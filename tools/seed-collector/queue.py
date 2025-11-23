"""Queue file operations for seed management."""

import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
import aiofiles
import aiofiles.os

from models import Seed, SeedStatus, QueueStats


class SeedQueue:
    """Manages the seed queue file (JSONL format)."""

    def __init__(self, queue_file: str):
        self.queue_file = Path(queue_file)
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Ensure queue file exists."""
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            self.queue_file.touch()

    async def add(self, seed: Seed) -> Seed:
        """Add a seed to the queue."""
        async with self._lock:
            async with aiofiles.open(self.queue_file, "a", encoding="utf-8") as f:
                line = seed.model_dump_json() + "\n"
                await f.write(line)
        return seed

    async def get_all(self, status: Optional[SeedStatus] = None) -> list[Seed]:
        """Get all seeds, optionally filtered by status."""
        seeds = []
        async with self._lock:
            if not self.queue_file.exists():
                return seeds
            async with aiofiles.open(self.queue_file, "r", encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        seed = Seed(**data)
                        if status is None or seed.status == status:
                            seeds.append(seed)
                    except (json.JSONDecodeError, ValueError):
                        continue
        return seeds

    async def get_by_id(self, seed_id: str) -> Optional[Seed]:
        """Get a specific seed by ID."""
        seeds = await self.get_all()
        for seed in seeds:
            if seed.id == seed_id:
                return seed
        return None

    async def update_status(self, seed_id: str, status: SeedStatus) -> bool:
        """Update the status of a seed."""
        async with self._lock:
            seeds = []
            found = False
            async with aiofiles.open(self.queue_file, "r", encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("id") == seed_id:
                            data["status"] = status.value
                            found = True
                        seeds.append(data)
                    except json.JSONDecodeError:
                        continue

            if found:
                async with aiofiles.open(self.queue_file, "w", encoding="utf-8") as f:
                    for seed_data in seeds:
                        await f.write(json.dumps(seed_data) + "\n")
            return found

    async def delete(self, seed_id: str) -> bool:
        """Delete a seed from the queue."""
        async with self._lock:
            seeds = []
            found = False
            async with aiofiles.open(self.queue_file, "r", encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("id") == seed_id:
                            found = True
                            continue  # Skip this seed (delete it)
                        seeds.append(data)
                    except json.JSONDecodeError:
                        continue

            if found:
                async with aiofiles.open(self.queue_file, "w", encoding="utf-8") as f:
                    for seed_data in seeds:
                        await f.write(json.dumps(seed_data) + "\n")
            return found

    async def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        seeds = await self.get_all()
        hosts = set()
        counts = {status: 0 for status in SeedStatus}

        for seed in seeds:
            counts[seed.status] += 1
            hosts.add(seed.host)

        return QueueStats(
            total=len(seeds),
            pending=counts[SeedStatus.PENDING],
            processing=counts[SeedStatus.PROCESSING],
            approved=counts[SeedStatus.APPROVED],
            rejected=counts[SeedStatus.REJECTED],
            unique_hosts=len(hosts),
        )

    async def get_pending_hosts(self) -> set[str]:
        """Get unique hosts from pending seeds."""
        seeds = await self.get_all(status=SeedStatus.PENDING)
        return {seed.host for seed in seeds}

    async def mark_host_processed(self, host: str, approved: bool):
        """Mark all seeds for a host as approved or rejected."""
        new_status = SeedStatus.APPROVED if approved else SeedStatus.REJECTED
        async with self._lock:
            seeds = []
            async with aiofiles.open(self.queue_file, "r", encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        seed = Seed(**data)
                        if seed.host == host and seed.status == SeedStatus.PENDING:
                            data["status"] = new_status.value
                        seeds.append(data)
                    except (json.JSONDecodeError, ValueError):
                        continue

            async with aiofiles.open(self.queue_file, "w", encoding="utf-8") as f:
                for seed_data in seeds:
                    await f.write(json.dumps(seed_data) + "\n")
