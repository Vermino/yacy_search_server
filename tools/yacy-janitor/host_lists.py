"""Host list management for keep/ban lists."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import aiofiles
import aiofiles.os
import asyncio
import structlog

from models import ClassificationResult

logger = structlog.get_logger()


class HostListManager:
    """Manages keep and ban host lists."""

    def __init__(
        self,
        keep_file: Path,
        ban_file: Path,
        review_file: Path,
        cache_file: Path,
    ):
        self.keep_file = keep_file
        self.ban_file = ban_file
        self.review_file = review_file
        self.cache_file = cache_file
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Ensure all files exist."""
        for f in [self.keep_file, self.ban_file]:
            f.parent.mkdir(parents=True, exist_ok=True)
            if not f.exists():
                f.touch()

        self.review_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.review_file.exists():
            self.review_file.touch()

    async def _load_list(self, path: Path) -> set[str]:
        """Load a host list from file."""
        hosts = set()
        if not path.exists():
            return hosts
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            async for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    hosts.add(line.lower())
        return hosts

    async def _save_list(self, path: Path, hosts: set[str]):
        """Save a host list to file."""
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(f"# Updated: {datetime.utcnow().isoformat()}\n")
            for host in sorted(hosts):
                await f.write(f"{host}\n")

    async def get_keep_hosts(self) -> set[str]:
        """Get the set of hosts to keep."""
        return await self._load_list(self.keep_file)

    async def get_ban_hosts(self) -> set[str]:
        """Get the set of banned hosts."""
        return await self._load_list(self.ban_file)

    async def get_all_known_hosts(self) -> set[str]:
        """Get all known hosts (keep + ban)."""
        keep = await self.get_keep_hosts()
        ban = await self.get_ban_hosts()
        return keep | ban

    async def add_to_keep(self, host: str) -> bool:
        """Add a host to the keep list."""
        async with self._lock:
            hosts = await self.get_keep_hosts()
            host_lower = host.lower()
            if host_lower in hosts:
                return False
            hosts.add(host_lower)
            await self._save_list(self.keep_file, hosts)
            logger.info("added_to_keep_list", host=host)
            return True

    async def add_to_ban(self, host: str) -> bool:
        """Add a host to the ban list."""
        async with self._lock:
            hosts = await self.get_ban_hosts()
            host_lower = host.lower()
            if host_lower in hosts:
                return False
            hosts.add(host_lower)
            await self._save_list(self.ban_file, hosts)
            logger.info("added_to_ban_list", host=host)
            return True

    async def remove_from_keep(self, host: str) -> bool:
        """Remove a host from the keep list."""
        async with self._lock:
            hosts = await self.get_keep_hosts()
            host_lower = host.lower()
            if host_lower not in hosts:
                return False
            hosts.discard(host_lower)
            await self._save_list(self.keep_file, hosts)
            return True

    async def remove_from_ban(self, host: str) -> bool:
        """Remove a host from the ban list."""
        async with self._lock:
            hosts = await self.get_ban_hosts()
            host_lower = host.lower()
            if host_lower not in hosts:
                return False
            hosts.discard(host_lower)
            await self._save_list(self.ban_file, hosts)
            return True

    async def add_to_review(self, result: ClassificationResult):
        """Add a classification result to the manual review queue."""
        async with self._lock:
            async with aiofiles.open(self.review_file, "a", encoding="utf-8") as f:
                data = result.model_dump()
                data["classified_at"] = data["classified_at"].isoformat()
                await f.write(json.dumps(data) + "\n")
        logger.info("added_to_review", host=result.host)

    async def get_review_queue(self) -> list[ClassificationResult]:
        """Get all items in the review queue."""
        results = []
        if not self.review_file.exists():
            return results
        async with aiofiles.open(self.review_file, "r", encoding="utf-8") as f:
            async for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    results.append(ClassificationResult(**data))
                except (json.JSONDecodeError, ValueError):
                    continue
        return results

    async def clear_review_item(self, host: str) -> bool:
        """Remove a host from the review queue."""
        async with self._lock:
            items = await self.get_review_queue()
            new_items = [i for i in items if i.host.lower() != host.lower()]
            if len(new_items) == len(items):
                return False

            async with aiofiles.open(self.review_file, "w", encoding="utf-8") as f:
                for item in new_items:
                    data = item.model_dump()
                    data["classified_at"] = data["classified_at"].isoformat()
                    await f.write(json.dumps(data) + "\n")
            return True

    # Classification cache methods
    async def get_cached_classification(self, host: str) -> Optional[ClassificationResult]:
        """Get a cached classification result."""
        if not self.cache_file.exists():
            return None
        async with aiofiles.open(self.cache_file, "r", encoding="utf-8") as f:
            content = await f.read()
            if not content:
                return None
            try:
                cache = json.loads(content)
                if host.lower() in cache:
                    data = cache[host.lower()]
                    return ClassificationResult(**data)
            except (json.JSONDecodeError, ValueError):
                pass
        return None

    async def cache_classification(self, result: ClassificationResult):
        """Cache a classification result."""
        async with self._lock:
            cache = {}
            if self.cache_file.exists():
                async with aiofiles.open(self.cache_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    if content:
                        try:
                            cache = json.loads(content)
                        except json.JSONDecodeError:
                            pass

            data = result.model_dump()
            data["classified_at"] = data["classified_at"].isoformat()
            cache[result.host.lower()] = data

            async with aiofiles.open(self.cache_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(cache, indent=2))
