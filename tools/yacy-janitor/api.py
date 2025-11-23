"""
Janitor API - HTTP endpoints for manual review and management.

Provides endpoints for:
- Viewing and managing the review queue
- Approving/rejecting hosts
- Viewing statistics
- Triggering seed generation
"""

import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_settings
from models import ClassificationResult, HostCategory, JanitorStats
from host_lists import HostListManager
from seed_generator import SeedGenerator
from yacy_client import YaCyClient

settings = get_settings()

# Initialize managers
host_lists = HostListManager(
    keep_file=settings.keep_hosts_file,
    ban_file=settings.ban_hosts_file,
    review_file=settings.manual_review_file,
    cache_file=settings.cache_file,
)

seed_generator = SeedGenerator(
    keep_hosts_file=settings.keep_hosts_file,
    ban_hosts_file=settings.ban_hosts_file,
    curated_seeds_file=settings.curated_seeds_file,
    mustmatch_file=settings.url_mustmatch_file,
    mustnotmatch_file=settings.url_mustnotmatch_file,
)

app = FastAPI(
    title="YaCy Janitor API",
    description="Manage host classification and review queue",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewDecision(BaseModel):
    """Decision for a host in review."""
    host: str
    action: str  # "keep", "ban", "skip"
    reason: Optional[str] = None


class HostListStats(BaseModel):
    """Statistics about host lists."""
    keep_count: int
    ban_count: int
    review_count: int


# ============= Review Queue Endpoints =============

@app.get("/review")
async def get_review_queue(limit: int = Query(100, ge=1, le=1000)):
    """Get items in the manual review queue."""
    await host_lists.initialize()
    items = await host_lists.get_review_queue()
    return {
        "items": [item.model_dump() for item in items[:limit]],
        "total": len(items),
    }


@app.post("/review/decide")
async def decide_review(decision: ReviewDecision):
    """Make a decision on a host in the review queue."""
    await host_lists.initialize()

    host = decision.host.lower()
    action = decision.action.lower()

    if action == "keep":
        await host_lists.add_to_keep(host)
        await host_lists.clear_review_item(host)
        return {"status": "ok", "message": f"Added {host} to keep list"}

    elif action == "ban":
        await host_lists.add_to_ban(host)
        await host_lists.clear_review_item(host)

        # Also delete from YaCy index
        async with YaCyClient(
            settings.yacy_url,
            settings.yacy_admin_user,
            settings.yacy_admin_password,
        ) as client:
            await client.delete_host(host)
            await client.add_to_blacklist(host, settings.yacy_blacklist_name)

        return {"status": "ok", "message": f"Banned {host} and deleted from index"}

    elif action == "skip":
        await host_lists.clear_review_item(host)
        return {"status": "ok", "message": f"Skipped {host} (removed from review)"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


@app.delete("/review/{host}")
async def remove_from_review(host: str):
    """Remove a host from the review queue without deciding."""
    await host_lists.initialize()
    removed = await host_lists.clear_review_item(host)
    if not removed:
        raise HTTPException(status_code=404, detail="Host not found in review queue")
    return {"status": "ok", "message": f"Removed {host} from review queue"}


# ============= Host List Endpoints =============

@app.get("/hosts/keep")
async def get_keep_hosts():
    """Get all hosts in the keep list."""
    await host_lists.initialize()
    hosts = await host_lists.get_keep_hosts()
    return {"hosts": sorted(hosts), "count": len(hosts)}


@app.get("/hosts/ban")
async def get_ban_hosts():
    """Get all hosts in the ban list."""
    await host_lists.initialize()
    hosts = await host_lists.get_ban_hosts()
    return {"hosts": sorted(hosts), "count": len(hosts)}


@app.post("/hosts/keep/{host}")
async def add_keep_host(host: str):
    """Manually add a host to the keep list."""
    await host_lists.initialize()
    added = await host_lists.add_to_keep(host.lower())
    if not added:
        return {"status": "ok", "message": f"{host} already in keep list"}
    return {"status": "ok", "message": f"Added {host} to keep list"}


@app.post("/hosts/ban/{host}")
async def add_ban_host(host: str, delete_from_index: bool = True):
    """Manually add a host to the ban list."""
    await host_lists.initialize()
    await host_lists.add_to_ban(host.lower())

    if delete_from_index:
        async with YaCyClient(
            settings.yacy_url,
            settings.yacy_admin_user,
            settings.yacy_admin_password,
        ) as client:
            await client.delete_host(host)
            await client.add_to_blacklist(host, settings.yacy_blacklist_name)

    return {"status": "ok", "message": f"Banned {host}"}


@app.delete("/hosts/keep/{host}")
async def remove_keep_host(host: str):
    """Remove a host from the keep list."""
    await host_lists.initialize()
    removed = await host_lists.remove_from_keep(host.lower())
    if not removed:
        raise HTTPException(status_code=404, detail="Host not found in keep list")
    return {"status": "ok", "message": f"Removed {host} from keep list"}


@app.delete("/hosts/ban/{host}")
async def remove_ban_host(host: str):
    """Remove a host from the ban list."""
    await host_lists.initialize()
    removed = await host_lists.remove_from_ban(host.lower())
    if not removed:
        raise HTTPException(status_code=404, detail="Host not found in ban list")
    return {"status": "ok", "message": f"Removed {host} from ban list"}


# ============= Stats Endpoints =============

@app.get("/stats", response_model=HostListStats)
async def get_stats():
    """Get statistics about host lists."""
    await host_lists.initialize()
    keep = await host_lists.get_keep_hosts()
    ban = await host_lists.get_ban_hosts()
    review = await host_lists.get_review_queue()
    return HostListStats(
        keep_count=len(keep),
        ban_count=len(ban),
        review_count=len(review),
    )


# ============= Seed Generation Endpoints =============

@app.post("/generate/seeds")
async def generate_seeds():
    """Generate curated seeds from keep hosts."""
    count = await seed_generator.generate_curated_seeds()
    return {"status": "ok", "seeds_generated": count}


@app.post("/generate/regex")
async def generate_regex():
    """Generate URL mustmatch/mustnotmatch regex patterns."""
    mustmatch = await seed_generator.generate_mustmatch_regex()
    mustnotmatch = await seed_generator.generate_mustnotmatch_regex()
    return {
        "status": "ok",
        "mustmatch": mustmatch,
        "mustnotmatch": mustnotmatch,
    }


@app.post("/generate/all")
async def generate_all():
    """Generate all seed files and regex patterns."""
    results = await seed_generator.generate_all()
    return {"status": "ok", **results}


# ============= Health Endpoint =============

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8092)
