"""YaCy API client for the Janitor service."""

import httpx
from typing import Optional
from urllib.parse import urljoin, quote
import structlog

from models import HostInfo, SampleDocument

logger = structlog.get_logger()


class YaCyClient:
    """Client for interacting with YaCy APIs."""

    def __init__(
        self,
        base_url: str,
        username: str = "admin",
        password: str = "yacy",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = (username, password)
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=self.auth,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Use async with context.")
        return self._client

    async def get_host_facets(self, limit: int = 10000) -> dict[str, int]:
        """Get host facets from the Solr index.

        Returns a dict mapping host -> document count.
        """
        try:
            # Use the search API with faceting
            params = {
                "query": "*:*",
                "maximumRecords": "0",
                "facet": "true",
                "facet.field": "host_s",
                "facet.limit": str(limit),
                "facet.mincount": "1",
            }
            response = await self.client.get("/yacysearch.json", params=params)
            response.raise_for_status()
            data = response.json()

            # Parse facet results
            hosts = {}
            facet_counts = data.get("facet_counts", {}).get("facet_fields", {}).get("host_s", [])

            # Facets come as [host1, count1, host2, count2, ...]
            for i in range(0, len(facet_counts), 2):
                if i + 1 < len(facet_counts):
                    host = facet_counts[i]
                    count = facet_counts[i + 1]
                    hosts[host] = count

            logger.info("fetched_host_facets", host_count=len(hosts))
            return hosts

        except Exception as e:
            logger.error("failed_to_fetch_hosts", error=str(e))
            # Fallback: try alternative approach using IndexBrowser
            return await self._get_hosts_fallback()

    async def _get_hosts_fallback(self) -> dict[str, int]:
        """Fallback method to get hosts using IndexBrowser API."""
        try:
            params = {"hosts": "", "facetcount": "10000"}
            response = await self.client.get("/IndexBrowser_p.json", params=params)
            response.raise_for_status()
            data = response.json()

            hosts = {}
            for item in data.get("hosts", []):
                host = item.get("host", "")
                count = item.get("count", 0)
                if host:
                    hosts[host] = count
            return hosts
        except Exception as e:
            logger.error("fallback_host_fetch_failed", error=str(e))
            return {}

    async def sample_documents(self, host: str, limit: int = 5) -> list[SampleDocument]:
        """Get sample documents for a specific host."""
        try:
            params = {
                "query": f'host_s:"{host}"',
                "maximumRecords": str(limit),
                "resource": "local",
            }
            response = await self.client.get("/yacysearch.json", params=params)
            response.raise_for_status()
            data = response.json()

            documents = []
            channels = data.get("channels", [])
            if channels:
                items = channels[0].get("items", [])
                for item in items:
                    doc = SampleDocument(
                        url=item.get("link", ""),
                        title=item.get("title", ""),
                        snippet=item.get("description", ""),
                        host=host,
                    )
                    documents.append(doc)

            logger.debug("sampled_documents", host=host, count=len(documents))
            return documents

        except Exception as e:
            logger.error("failed_to_sample_documents", host=host, error=str(e))
            return []

    async def get_host_info(self, host: str, sample_limit: int = 5) -> HostInfo:
        """Get detailed information about a host."""
        docs = await self.sample_documents(host, limit=sample_limit)
        return HostInfo(
            host=host,
            doc_count=len(docs),
            sample_titles=[d.title for d in docs if d.title],
            sample_urls=[d.url for d in docs if d.url],
            sample_snippets=[d.snippet for d in docs if d.snippet],
        )

    async def delete_host(self, host: str) -> bool:
        """Delete all documents for a host from the index."""
        try:
            # Use the IndexDeletion API
            data = {
                "engage-querydelete": "on",
                "querydelete": f'host_s:"{host}"',
            }
            response = await self.client.post(
                "/IndexDeletion_p.html",
                data=data,
            )
            response.raise_for_status()
            logger.info("deleted_host_from_index", host=host)
            return True

        except Exception as e:
            logger.error("failed_to_delete_host", host=host, error=str(e))
            return False

    async def get_blacklists(self) -> list[str]:
        """Get list of available blacklists."""
        try:
            response = await self.client.get("/api/blacklists_p.json")
            response.raise_for_status()
            data = response.json()

            blacklists = []
            for bl in data.get("lists", []):
                name = bl.get("name", "")
                if name:
                    blacklists.append(name)
            return blacklists

        except Exception as e:
            logger.error("failed_to_get_blacklists", error=str(e))
            return []

    async def add_to_blacklist(self, host: str, blacklist_name: str = "blacklist.black") -> bool:
        """Add a host to a YaCy blacklist."""
        try:
            # The blacklist entry format is "host/.*" to block all paths
            entry = f"{host}/.*"

            data = {
                "addBlacklistEntry": entry,
                "currentBlacklist": blacklist_name,
                "selectList": blacklist_name,
            }
            response = await self.client.post("/Blacklist_p.html", data=data)
            response.raise_for_status()
            logger.info("added_to_blacklist", host=host, blacklist=blacklist_name)
            return True

        except Exception as e:
            logger.error("failed_to_add_to_blacklist", host=host, error=str(e))
            return False

    async def health_check(self) -> bool:
        """Check if YaCy is reachable."""
        try:
            response = await self.client.get("/api/status_p.json")
            return response.status_code == 200
        except Exception:
            return False

    async def get_index_size(self) -> int:
        """Get the total number of documents in the index."""
        try:
            response = await self.client.get("/api/status_p.json")
            response.raise_for_status()
            data = response.json()
            return int(data.get("indexCount", 0))
        except Exception as e:
            logger.error("failed_to_get_index_size", error=str(e))
            return 0
