"""
YaCy Janitor Service

A service that scans hosts in the YaCy index, classifies them using
hardcoded rules and LLM, and takes actions (keep/ban/delete).
"""

import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import structlog

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import get_settings, Settings
from models import HostCategory, ClassificationResult, HostInfo, JanitorStats
from yacy_client import YaCyClient
from classifier import LLMClassifier, MockLLMClassifier
from hardcoded_rules import classify_by_rules
from host_lists import HostListManager

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


class YaCyJanitor:
    """Main janitor service class."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.host_lists = HostListManager(
            keep_file=settings.keep_hosts_file,
            ban_file=settings.ban_hosts_file,
            review_file=settings.manual_review_file,
            cache_file=settings.cache_file,
        )
        self.classifier: Optional[LLMClassifier] = None
        self.stats = JanitorStats()
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize the janitor."""
        await self.host_lists.initialize()

        # Initialize classifier if API key is available
        if self.settings.llm_api_key:
            self.classifier = LLMClassifier(self.settings)
            logger.info("llm_classifier_initialized", model=self.settings.llm_model)
        else:
            logger.warning("no_llm_api_key", message="Running without LLM classification")

    async def scan_hosts(self):
        """Scan hosts from YaCy index and queue new ones for classification."""
        logger.info("starting_host_scan")
        self.stats.last_scan = datetime.utcnow()

        try:
            async with YaCyClient(
                self.settings.yacy_url,
                self.settings.yacy_admin_user,
                self.settings.yacy_admin_password,
            ) as client:
                # Get host facets from index
                host_facets = await client.get_host_facets(limit=10000)

                if not host_facets:
                    logger.warning("no_hosts_found")
                    return

                # Get already-known hosts
                known_hosts = await self.host_lists.get_all_known_hosts()

                # Find new hosts
                new_hosts = set(host_facets.keys()) - known_hosts

                logger.info(
                    "host_scan_complete",
                    total_hosts=len(host_facets),
                    known_hosts=len(known_hosts),
                    new_hosts=len(new_hosts),
                )

                self.stats.total_hosts_scanned = len(host_facets)

                # Process new hosts
                if new_hosts:
                    await self._process_new_hosts(client, list(new_hosts))

        except Exception as e:
            logger.error("host_scan_error", error=str(e))

    async def _process_new_hosts(self, client: YaCyClient, hosts: list[str]):
        """Process a batch of new hosts."""
        batch_size = self.settings.max_hosts_per_batch
        hosts_to_process = hosts[:batch_size]

        logger.info("processing_new_hosts", count=len(hosts_to_process))

        for host in hosts_to_process:
            await self._classify_and_act(client, host)

    async def _classify_and_act(self, client: YaCyClient, host: str):
        """Classify a single host and take appropriate action."""
        # First, try hardcoded rules (fast path)
        result = classify_by_rules(host)

        if result:
            logger.info(
                "hardcoded_classification",
                host=host,
                category=result.category.value,
            )
        elif self.classifier:
            # Need LLM classification - get sample documents first
            host_info = await client.get_host_info(
                host, sample_limit=self.settings.sample_docs_per_host
            )

            if host_info.doc_count == 0:
                logger.debug("no_samples_for_host", host=host)
                return

            result = await self.classifier.classify(host_info)
        else:
            # No classifier available, mark as unsure
            result = ClassificationResult(
                host=host,
                category=HostCategory.UNSURE,
                confidence=0.0,
                reason="No classifier available",
                source="none",
            )

        # Take action based on classification
        await self._take_action(client, result)

        # Cache the result
        await self.host_lists.cache_classification(result)

    async def _take_action(self, client: YaCyClient, result: ClassificationResult):
        """Take action based on classification result."""
        host = result.host
        category = result.category
        confidence = result.confidence

        if category == HostCategory.KEEP and confidence >= self.settings.keep_confidence_threshold:
            # Add to keep list
            await self.host_lists.add_to_keep(host)
            self.stats.hosts_kept += 1
            logger.info("action_keep", host=host, confidence=confidence)

        elif category.is_ban() and confidence >= self.settings.ban_confidence_threshold:
            # Add to ban list, YaCy blacklist, and delete from index
            await self.host_lists.add_to_ban(host)

            # Add to YaCy's blacklist file
            blacklist_added = await client.add_to_blacklist(
                host,
                self.settings.yacy_blacklist_name
            )

            # Delete from index
            deleted = await client.delete_host(host)

            self.stats.hosts_banned += 1
            logger.info(
                "action_ban",
                host=host,
                category=category.value,
                confidence=confidence,
                blacklist_added=blacklist_added,
                deleted=deleted,
            )

        else:
            # Add to manual review queue
            await self.host_lists.add_to_review(result)
            self.stats.hosts_pending_review += 1
            logger.info(
                "action_review",
                host=host,
                category=category.value,
                confidence=confidence,
            )

    async def process_seed_queue(self):
        """Process incoming seeds from the collector."""
        logger.info("processing_seed_queue")

        queue_file = self.settings.queue_file
        if not queue_file.exists():
            return

        # Read pending seeds
        pending_hosts = set()
        seeds = []

        try:
            with open(queue_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("status") == "pending":
                            host = data.get("host", "")
                            if host:
                                pending_hosts.add(host)
                            seeds.append(data)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error("seed_queue_read_error", error=str(e))
            return

        if not pending_hosts:
            return

        logger.info("found_pending_seed_hosts", count=len(pending_hosts))

        # Get already-known hosts
        known_hosts = await self.host_lists.get_all_known_hosts()
        new_hosts = pending_hosts - known_hosts

        if new_hosts:
            async with YaCyClient(
                self.settings.yacy_url,
                self.settings.yacy_admin_user,
                self.settings.yacy_admin_password,
            ) as client:
                for host in list(new_hosts)[:self.settings.max_hosts_per_batch]:
                    await self._classify_and_act(client, host)

    async def run_once(self):
        """Run a single scan and classification cycle."""
        await self.initialize()
        await self.scan_hosts()
        await self.process_seed_queue()

    async def run_scheduled(self):
        """Run the janitor with scheduled jobs."""
        await self.initialize()

        scheduler = AsyncIOScheduler()

        # Host scanning job
        scheduler.add_job(
            self.scan_hosts,
            IntervalTrigger(minutes=self.settings.host_scan_interval_minutes),
            id="host_scan",
            name="Scan hosts from YaCy index",
        )

        # Seed queue processing job
        scheduler.add_job(
            self.process_seed_queue,
            IntervalTrigger(minutes=self.settings.seed_intake_interval_minutes),
            id="seed_intake",
            name="Process seed queue",
        )

        scheduler.start()
        logger.info(
            "scheduler_started",
            host_scan_interval=self.settings.host_scan_interval_minutes,
            seed_intake_interval=self.settings.seed_intake_interval_minutes,
        )

        # Run initial scan
        await self.scan_hosts()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        scheduler.shutdown()
        logger.info("scheduler_stopped")

    def shutdown(self):
        """Signal shutdown."""
        self._shutdown_event.set()


async def main():
    """Main entry point."""
    settings = get_settings()
    janitor = YaCyJanitor(settings)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("shutdown_signal_received")
        janitor.shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Check command line args
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Single run mode
        await janitor.run_once()
    else:
        # Scheduled mode
        await janitor.run_scheduled()


if __name__ == "__main__":
    asyncio.run(main())
