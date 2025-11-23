"""Data models for the Seed Collector service."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl
import hashlib
import uuid


class SeedStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    ERROR = "error"


class SeedInput(BaseModel):
    """Input model for adding a new seed."""
    url: str = Field(..., description="URL to add as a seed")
    title: Optional[str] = Field(None, description="Page title")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    notes: Optional[str] = Field(None, description="Optional notes")


class Seed(BaseModel):
    """Full seed record."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    url: str
    host: str
    title: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: SeedStatus = SeedStatus.PENDING

    @classmethod
    def from_input(cls, seed_input: SeedInput) -> "Seed":
        """Create a Seed from SeedInput."""
        from urllib.parse import urlparse
        parsed = urlparse(seed_input.url)
        host = parsed.netloc.lower()
        # Remove www. prefix for consistency
        if host.startswith("www."):
            host = host[4:]
        return cls(
            url=seed_input.url,
            host=host,
            title=seed_input.title,
            tags=seed_input.tags,
            notes=seed_input.notes,
        )


class SeedResponse(BaseModel):
    """Response after adding a seed."""
    status: str
    id: str
    message: str


class QueueStats(BaseModel):
    """Statistics about the seed queue."""
    total: int
    pending: int
    processing: int
    approved: int
    rejected: int
    unique_hosts: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    queue_file: str
    queue_size: int
