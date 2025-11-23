"""
Seed Generator - Creates curated seed files and URL regex patterns from host lists.

This module generates:
1. curated_seeds.txt - URLs for YaCy to crawl
2. url_mustmatch.regex - Regex pattern for crawler URL filtering (whitelist)
3. url_mustnotmatch.regex - Regex pattern for crawler URL filtering (blacklist)
"""

import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
import aiofiles
import structlog

logger = structlog.get_logger()


def escape_regex(host: str) -> str:
    """Escape a hostname for use in regex."""
    return re.escape(host).replace(r"\.", r"\.")


def generate_mustmatch_regex(hosts: set[str]) -> str:
    """
    Generate a URL mustmatch regex from a set of hosts.

    The regex matches URLs from any of the given hosts.
    Format: ^https?://([^/]+\.)?(host1\.com|host2\.org)/.*
    """
    if not hosts:
        return ".*"  # Match everything if no hosts specified

    escaped_hosts = [escape_regex(h) for h in sorted(hosts)]
    host_pattern = "|".join(escaped_hosts)

    # Match with or without www. prefix and subdomains
    return f"^https?://([^/]+\\.)?({host_pattern})/.*"


def generate_mustnotmatch_regex(hosts: set[str]) -> str:
    """
    Generate a URL mustnotmatch regex from a set of banned hosts.

    The regex matches URLs from any of the banned hosts.
    """
    if not hosts:
        return "^$"  # Match nothing if no hosts specified

    escaped_hosts = [escape_regex(h) for h in sorted(hosts)]
    host_pattern = "|".join(escaped_hosts)

    return f"^https?://([^/]+\\.)?({host_pattern})/.*"


def generate_seed_urls(hosts: set[str], protocol: str = "https") -> list[str]:
    """Generate seed URLs from a set of hosts."""
    urls = []
    for host in sorted(hosts):
        # Add both with and without www
        urls.append(f"{protocol}://{host}/")
        if not host.startswith("www."):
            urls.append(f"{protocol}://www.{host}/")
    return urls


class SeedGenerator:
    """Generates seed files and regex patterns from host lists."""

    def __init__(
        self,
        keep_hosts_file: Path,
        ban_hosts_file: Path,
        curated_seeds_file: Path,
        mustmatch_file: Path,
        mustnotmatch_file: Path,
    ):
        self.keep_hosts_file = keep_hosts_file
        self.ban_hosts_file = ban_hosts_file
        self.curated_seeds_file = curated_seeds_file
        self.mustmatch_file = mustmatch_file
        self.mustnotmatch_file = mustnotmatch_file

    async def _load_hosts(self, path: Path) -> set[str]:
        """Load hosts from a file."""
        hosts = set()
        if not path.exists():
            return hosts
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            async for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    hosts.add(line.lower())
        return hosts

    async def _write_file(self, path: Path, content: str, header: str = ""):
        """Write content to a file with optional header."""
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            if header:
                await f.write(f"# {header}\n")
                await f.write(f"# Generated: {datetime.utcnow().isoformat()}\n\n")
            await f.write(content)

    async def generate_curated_seeds(self) -> int:
        """Generate curated_seeds.txt from keep_hosts.txt."""
        keep_hosts = await self._load_hosts(self.keep_hosts_file)

        if not keep_hosts:
            logger.warning("no_keep_hosts", message="No hosts to generate seeds from")
            return 0

        seed_urls = generate_seed_urls(keep_hosts)
        content = "\n".join(seed_urls) + "\n"

        await self._write_file(
            self.curated_seeds_file,
            content,
            header="Curated seed URLs for YaCy crawling"
        )

        logger.info("generated_curated_seeds", count=len(seed_urls))
        return len(seed_urls)

    async def generate_mustmatch_regex(self) -> str:
        """Generate URL mustmatch regex from keep_hosts.txt."""
        keep_hosts = await self._load_hosts(self.keep_hosts_file)
        regex = generate_mustmatch_regex(keep_hosts)

        await self._write_file(
            self.mustmatch_file,
            regex + "\n",
            header="URL Mustmatch regex for YaCy crawler"
        )

        logger.info("generated_mustmatch_regex", host_count=len(keep_hosts))
        return regex

    async def generate_mustnotmatch_regex(self) -> str:
        """Generate URL mustnotmatch regex from ban_hosts.txt."""
        ban_hosts = await self._load_hosts(self.ban_hosts_file)
        regex = generate_mustnotmatch_regex(ban_hosts)

        await self._write_file(
            self.mustnotmatch_file,
            regex + "\n",
            header="URL Mustnotmatch regex for YaCy crawler"
        )

        logger.info("generated_mustnotmatch_regex", host_count=len(ban_hosts))
        return regex

    async def generate_all(self) -> dict:
        """Generate all seed files and regex patterns."""
        results = {
            "curated_seeds_count": await self.generate_curated_seeds(),
            "mustmatch_regex": await self.generate_mustmatch_regex(),
            "mustnotmatch_regex": await self.generate_mustnotmatch_regex(),
        }
        return results


async def main():
    """CLI entry point for seed generation."""
    import sys
    from config import get_settings

    settings = get_settings()

    generator = SeedGenerator(
        keep_hosts_file=settings.keep_hosts_file,
        ban_hosts_file=settings.ban_hosts_file,
        curated_seeds_file=settings.curated_seeds_file,
        mustmatch_file=settings.url_mustmatch_file,
        mustnotmatch_file=settings.url_mustnotmatch_file,
    )

    results = await generator.generate_all()

    print(f"Generated {results['curated_seeds_count']} seed URLs")
    print(f"Mustmatch regex: {results['mustmatch_regex'][:80]}...")
    print(f"Mustnotmatch regex: {results['mustnotmatch_regex'][:80]}...")


if __name__ == "__main__":
    asyncio.run(main())
