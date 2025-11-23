"""
YaCy Seed Collector Service

A lightweight FastAPI service for collecting URLs while browsing.
Works with browser extensions, bookmarklets, and mobile share targets.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from models import (
    Seed,
    SeedInput,
    SeedResponse,
    SeedStatus,
    QueueStats,
    HealthResponse,
)
from queue import SeedQueue

# Configuration
QUEUE_FILE = os.environ.get("QUEUE_FILE", "/data/queued_seeds.jsonl")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8091"))
STATIC_DIR = Path(__file__).parent / "static"

# Initialize queue
seed_queue = SeedQueue(QUEUE_FILE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    await seed_queue.initialize()
    yield


app = FastAPI(
    title="YaCy Seed Collector",
    description="Collect URLs for YaCy search index curation",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for browser extensions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Landing page with bookmarklet."""
    stats = await seed_queue.get_stats()
    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8091")
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>YaCy Seed Collector</title>
        <link rel="manifest" href="/static/manifest.json">
        <meta name="theme-color" content="#2563eb">
        <link rel="apple-touch-icon" href="/static/icon-192.png">
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
            .bookmarklet {{ display: inline-block; padding: 10px 20px; background: #2563eb; color: white;
                           text-decoration: none; border-radius: 6px; margin: 10px 0; }}
            .bookmarklet:hover {{ background: #1d4ed8; }}
            code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }}
            pre {{ background: #f1f5f9; padding: 15px; border-radius: 6px; overflow-x: auto; }}
            .stats {{ background: #f8fafc; padding: 15px; border-radius: 6px; margin: 20px 0; }}
            .install-btn {{ display: none; padding: 10px 20px; background: #22c55e; color: white;
                           border: none; border-radius: 6px; cursor: pointer; margin: 10px 0; }}
            .install-btn.show {{ display: inline-block; }}
        </style>
    </head>
    <body>
        <h1>YaCy Seed Collector</h1>
        <p>Add URLs to your YaCy curated seed list while browsing.</p>

        <div class="stats">
            <h3>Queue Statistics</h3>
            <p>Total seeds: <strong>{stats.total}</strong></p>
            <p>Pending: <strong>{stats.pending}</strong></p>
            <p>Unique hosts: <strong>{stats.unique_hosts}</strong></p>
        </div>

        <h2>Bookmarklet</h2>
        <p>Drag this link to your bookmarks bar:</p>
        <a class="bookmarklet" href="javascript:(function(){{var t=document.title;fetch('{os.environ.get("PUBLIC_URL", "http://localhost:8091")}/seed',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{url:location.href,title:t}})}}).then(r=>r.json()).then(d=>alert('Added: '+d.message)).catch(e=>alert('Error: '+e))}})();">
            + Add to YaCy Seeds
        </a>

        <h2>API Usage</h2>
        <pre>
# Add a seed
curl -X POST {os.environ.get("PUBLIC_URL", "http://localhost:8091")}/seed \\
  -H "Content-Type: application/json" \\
  -d '{{"url": "https://example.com", "tags": ["tech"]}}'

# View queue
curl {os.environ.get("PUBLIC_URL", "http://localhost:8091")}/queue

# Get stats
curl {os.environ.get("PUBLIC_URL", "http://localhost:8091")}/queue/stats
        </pre>

        <h2>Endpoints</h2>
        <ul>
            <li><code>POST /seed</code> - Add a URL to the queue</li>
            <li><code>GET /queue</code> - List all seeds</li>
            <li><code>GET /queue/stats</code> - Queue statistics</li>
            <li><code>DELETE /queue/{{id}}</code> - Remove a seed</li>
            <li><code>GET /health</code> - Health check</li>
        </ul>
    </body>
    </html>
    """


@app.post("/seed", response_model=SeedResponse)
async def add_seed(seed_input: SeedInput):
    """Add a URL to the seed queue."""
    try:
        seed = Seed.from_input(seed_input)
        await seed_queue.add(seed)
        return SeedResponse(
            status="ok",
            id=seed.id,
            message=f"Added {seed.host} to queue",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue", response_model=list[Seed])
async def get_queue(
    status: Optional[SeedStatus] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
):
    """Get seeds from the queue."""
    seeds = await seed_queue.get_all(status=status)
    return seeds[:limit]


@app.get("/queue/stats", response_model=QueueStats)
async def get_queue_stats():
    """Get queue statistics."""
    return await seed_queue.get_stats()


@app.get("/queue/{seed_id}", response_model=Seed)
async def get_seed(seed_id: str):
    """Get a specific seed by ID."""
    seed = await seed_queue.get_by_id(seed_id)
    if not seed:
        raise HTTPException(status_code=404, detail="Seed not found")
    return seed


@app.delete("/queue/{seed_id}")
async def delete_seed(seed_id: str):
    """Delete a seed from the queue."""
    deleted = await seed_queue.delete(seed_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Seed not found")
    return {"status": "ok", "message": f"Deleted seed {seed_id}"}


@app.patch("/queue/{seed_id}/status")
async def update_seed_status(seed_id: str, status: SeedStatus):
    """Update the status of a seed."""
    updated = await seed_queue.update_status(seed_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="Seed not found")
    return {"status": "ok", "message": f"Updated seed {seed_id} to {status.value}"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    stats = await seed_queue.get_stats()
    return HealthResponse(
        status="healthy",
        queue_file=QUEUE_FILE,
        queue_size=stats.total,
    )


@app.get("/hosts")
async def get_pending_hosts():
    """Get unique hosts from pending seeds."""
    hosts = await seed_queue.get_pending_hosts()
    return {"hosts": sorted(hosts), "count": len(hosts)}


@app.post("/share")
async def share_target(
    title: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
):
    """
    PWA Web Share Target endpoint.

    Receives shared content from mobile devices and adds URLs to the queue.
    """
    # Try to extract URL from the shared content
    shared_url = url

    # If no URL, try to find one in the text
    if not shared_url and text:
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        if urls:
            shared_url = urls[0]

    if not shared_url:
        # Redirect back with error
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>Share Failed</title></head>
        <body>
            <h1>No URL found</h1>
            <p>Could not find a URL in the shared content.</p>
            <a href="/">Go back</a>
        </body>
        </html>
        """, status_code=400)

    # Create and add the seed
    seed_input = SeedInput(url=shared_url, title=title or "")
    seed = Seed.from_input(seed_input)
    await seed_queue.add(seed)

    # Show success page
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Added to Seeds</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: system-ui; padding: 20px; text-align: center; }}
            .success {{ color: #22c55e; font-size: 48px; }}
            .url {{ word-break: break-all; color: #64748b; }}
        </style>
    </head>
    <body>
        <div class="success">✓</div>
        <h1>Added to Seeds</h1>
        <p class="url">{seed.host}</p>
        <p>The URL has been added to your seed queue.</p>
    </body>
    </html>
    """)


@app.get("/bookmarklet", response_class=HTMLResponse)
async def bookmarklet_page():
    """Serve the interactive bookmarklet setup page."""
    bookmarklet_file = STATIC_DIR / "bookmarklet.html"
    if bookmarklet_file.exists():
        return FileResponse(bookmarklet_file)
    return HTMLResponse("<h1>Bookmarklet page not found</h1>", status_code=404)


# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
