"""Configuration management for YaCy Janitor."""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # YaCy connection
    yacy_url: str = Field(default="http://localhost:8090", description="YaCy base URL")
    yacy_admin_user: str = Field(default="admin", description="YaCy admin username")
    yacy_admin_password: str = Field(default="yacy", description="YaCy admin password")
    yacy_blacklist_name: str = Field(default="blacklist.black", description="YaCy blacklist file name")

    # LLM configuration
    llm_provider: str = Field(default="openai", description="LLM provider: openai, anthropic, local")
    llm_api_key: Optional[str] = Field(default=None, description="LLM API key")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model name")
    llm_base_url: Optional[str] = Field(default=None, description="Custom LLM API base URL")

    # Data paths
    data_dir: Path = Field(default=Path("/data"), description="Data directory")
    queue_file: Path = Field(default=Path("/data/queued_seeds.jsonl"))
    keep_hosts_file: Path = Field(default=Path("/data/keep_hosts.txt"))
    ban_hosts_file: Path = Field(default=Path("/data/ban_hosts.txt"))
    manual_review_file: Path = Field(default=Path("/data/manual_review.jsonl"))
    cache_file: Path = Field(default=Path("/data/classification_cache.json"))
    curated_seeds_file: Path = Field(default=Path("/data/curated_seeds.txt"))
    url_mustmatch_file: Path = Field(default=Path("/data/url_mustmatch.regex"))
    url_mustnotmatch_file: Path = Field(default=Path("/data/url_mustnotmatch.regex"))

    # Git auto-commit
    git_auto_commit: bool = Field(default=False, description="Auto-commit host list changes")
    git_repo_path: Optional[Path] = Field(default=None, description="Git repository path for seeds")

    # Classification thresholds
    keep_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    ban_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)

    # Scheduling
    host_scan_interval_minutes: int = Field(default=60)
    classification_interval_minutes: int = Field(default=15)
    seed_intake_interval_minutes: int = Field(default=5)

    # Limits
    max_hosts_per_batch: int = Field(default=50)
    sample_docs_per_host: int = Field(default=5)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
