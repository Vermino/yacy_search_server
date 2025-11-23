"""Data models for the YaCy Janitor service."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class HostCategory(str, Enum):
    """Classification categories for hosts."""
    KEEP = "keep"
    BAN_MEDIA = "ban_media"
    BAN_SOCIAL = "ban_social"
    BAN_ECOM = "ban_ecom"
    BAN_NEWS = "ban_news"
    BAN_SPAM = "ban_spam"
    BAN_ADULT = "ban_adult"
    UNSURE = "unsure"

    def is_ban(self) -> bool:
        """Check if this category is a ban category."""
        return self.value.startswith("ban_")


class ClassificationResult(BaseModel):
    """Result of host classification."""
    host: str
    category: HostCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    sample_count: int = 0
    classified_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "llm"  # "llm", "hardcoded", "manual"


class HostInfo(BaseModel):
    """Information about a host from YaCy index."""
    host: str
    doc_count: int = 0
    sample_titles: list[str] = Field(default_factory=list)
    sample_urls: list[str] = Field(default_factory=list)
    sample_snippets: list[str] = Field(default_factory=list)


class SampleDocument(BaseModel):
    """A sample document from the YaCy index."""
    url: str
    title: str = ""
    snippet: str = ""
    host: str = ""


class JanitorStats(BaseModel):
    """Statistics about janitor operations."""
    total_hosts_scanned: int = 0
    hosts_kept: int = 0
    hosts_banned: int = 0
    hosts_pending_review: int = 0
    last_scan: Optional[datetime] = None
    last_classification: Optional[datetime] = None


class ActionResult(BaseModel):
    """Result of an action taken by the janitor."""
    action: str
    host: str
    success: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
