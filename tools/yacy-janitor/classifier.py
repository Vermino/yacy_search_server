"""LLM-based host classifier for the YaCy Janitor."""

import json
from typing import Optional
import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import HostCategory, ClassificationResult, HostInfo
from config import Settings

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a classifier for a niche search engine focused on:
- Technical/informational content (programming, DIY, tutorials)
- Homesteading, gardening, self-sufficiency
- Economics, finance education
- Obscure/long-form content
- Educational resources
- Personal blogs with substantive content

You should STRONGLY BAN:
- Mainstream video/audio platforms (YouTube, TikTok, Spotify, podcasts)
- Big social media (Facebook, Twitter/X, Instagram, Reddit, Discord)
- Big e-commerce (Amazon, eBay, Walmart, major retailers)
- Mainstream news outlets (CNN, NYT, BBC, Fox, etc.)
- SEO spam sites, content farms, scraper sites
- Adult content

For each host, analyze the provided sample URLs, titles, and snippets.

Respond ONLY with valid JSON in this exact format:
{
  "category": "keep|ban_media|ban_social|ban_ecom|ban_news|ban_spam|ban_adult|unsure",
  "confidence": 0.0-1.0,
  "reason": "Brief explanation (max 100 chars)"
}

Categories:
- keep: Good content matching our focus areas
- ban_media: Video/audio/streaming platforms
- ban_social: Social media platforms
- ban_ecom: E-commerce sites
- ban_news: Mainstream news outlets
- ban_spam: SEO spam, content farms, low-quality sites
- ban_adult: Adult/NSFW content
- unsure: Cannot determine, needs human review"""


class LLMClassifier:
    """Classifier using LLM to categorize hosts."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            kwargs = {"api_key": self.settings.llm_api_key}
            if self.settings.llm_base_url:
                kwargs["base_url"] = self.settings.llm_base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    def _format_host_info(self, host_info: HostInfo) -> str:
        """Format host info for the LLM prompt."""
        parts = [f"Host: {host_info.host}"]
        parts.append(f"Documents indexed: {host_info.doc_count}")

        if host_info.sample_urls:
            parts.append("\nSample URLs:")
            for url in host_info.sample_urls[:5]:
                parts.append(f"  - {url}")

        if host_info.sample_titles:
            parts.append("\nSample Titles:")
            for title in host_info.sample_titles[:5]:
                parts.append(f"  - {title}")

        if host_info.sample_snippets:
            parts.append("\nSample Snippets:")
            for snippet in host_info.sample_snippets[:3]:
                # Truncate long snippets
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                parts.append(f"  - {snippet}")

        return "\n".join(parts)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def classify(self, host_info: HostInfo) -> ClassificationResult:
        """Classify a host using the LLM."""
        user_message = self._format_host_info(host_info)

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=150,
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON response
            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            category_str = result.get("category", "unsure").lower()
            try:
                category = HostCategory(category_str)
            except ValueError:
                category = HostCategory.UNSURE

            confidence = float(result.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

            reason = result.get("reason", "No reason provided")[:100]

            logger.info(
                "llm_classification",
                host=host_info.host,
                category=category.value,
                confidence=confidence,
            )

            return ClassificationResult(
                host=host_info.host,
                category=category,
                confidence=confidence,
                reason=reason,
                sample_count=host_info.doc_count,
                source="llm",
            )

        except json.JSONDecodeError as e:
            logger.error("llm_json_parse_error", host=host_info.host, error=str(e))
            return ClassificationResult(
                host=host_info.host,
                category=HostCategory.UNSURE,
                confidence=0.0,
                reason=f"JSON parse error: {str(e)[:50]}",
                source="llm_error",
            )

        except Exception as e:
            logger.error("llm_classification_error", host=host_info.host, error=str(e))
            return ClassificationResult(
                host=host_info.host,
                category=HostCategory.UNSURE,
                confidence=0.0,
                reason=f"Classification error: {str(e)[:50]}",
                source="llm_error",
            )

    async def classify_batch(
        self, host_infos: list[HostInfo]
    ) -> list[ClassificationResult]:
        """Classify multiple hosts (sequentially to respect rate limits)."""
        results = []
        for host_info in host_infos:
            result = await self.classify(host_info)
            results.append(result)
        return results


class MockLLMClassifier(LLMClassifier):
    """Mock classifier for testing without LLM API."""

    async def classify(self, host_info: HostInfo) -> ClassificationResult:
        """Return a mock classification based on simple heuristics."""
        host = host_info.host.lower()

        # Simple heuristics for testing
        if any(kw in host for kw in ["blog", "wiki", "docs", "tutorial"]):
            return ClassificationResult(
                host=host_info.host,
                category=HostCategory.KEEP,
                confidence=0.7,
                reason="Mock: looks like informational content",
                source="mock",
            )

        return ClassificationResult(
            host=host_info.host,
            category=HostCategory.UNSURE,
            confidence=0.5,
            reason="Mock: could not determine",
            source="mock",
        )
