"""Hardcoded rules for fast-path host classification.

These rules bypass the LLM for known domains to save API costs and increase speed.
"""

import re
from typing import Optional
from models import HostCategory, ClassificationResult


# Major media/video platforms
MEDIA_PATTERNS = [
    r".*\.youtube\.com$",
    r".*\.youtu\.be$",
    r".*\.vimeo\.com$",
    r".*\.dailymotion\.com$",
    r".*\.twitch\.tv$",
    r".*\.tiktok\.com$",
    r".*\.spotify\.com$",
    r".*\.soundcloud\.com$",
    r".*\.podcasts\.apple\.com$",
    r".*\.music\.apple\.com$",
    r".*\.netflix\.com$",
    r".*\.hulu\.com$",
    r".*\.disneyplus\.com$",
    r".*\.hbomax\.com$",
    r".*\.primevideo\.com$",
    r".*\.pandora\.com$",
    r".*\.deezer\.com$",
    r".*\.bandcamp\.com$",
    r".*\.mixcloud\.com$",
    r".*\.rumble\.com$",
    r".*\.bitchute\.com$",
    r".*\.odysee\.com$",
]

# Major social media platforms
SOCIAL_PATTERNS = [
    r".*\.facebook\.com$",
    r".*\.fb\.com$",
    r".*\.instagram\.com$",
    r".*\.twitter\.com$",
    r".*\.x\.com$",
    r".*\.linkedin\.com$",
    r".*\.pinterest\.com$",
    r".*\.snapchat\.com$",
    r".*\.reddit\.com$",
    r".*\.tumblr\.com$",
    r".*\.discord\.com$",
    r".*\.discord\.gg$",
    r".*\.telegram\.org$",
    r".*\.t\.me$",
    r".*\.whatsapp\.com$",
    r".*\.wechat\.com$",
    r".*\.weixin\.qq\.com$",
    r".*\.threads\.net$",
    r".*\.mastodon\.social$",
    r".*\.bsky\.app$",
    r".*\.truth\.social$",
    r".*\.parler\.com$",
    r".*\.gab\.com$",
    r".*\.gettr\.com$",
    r".*\.nextdoor\.com$",
    r".*\.quora\.com$",
]

# Major e-commerce platforms
ECOM_PATTERNS = [
    r".*\.amazon\.com$",
    r".*\.amazon\.[a-z]{2,3}$",
    r".*\.ebay\.com$",
    r".*\.ebay\.[a-z]{2,3}$",
    r".*\.walmart\.com$",
    r".*\.target\.com$",
    r".*\.aliexpress\.com$",
    r".*\.alibaba\.com$",
    r".*\.wish\.com$",
    r".*\.etsy\.com$",
    r".*\.shopify\.com$",
    r".*\.bestbuy\.com$",
    r".*\.newegg\.com$",
    r".*\.wayfair\.com$",
    r".*\.overstock\.com$",
    r".*\.homedepot\.com$",
    r".*\.lowes\.com$",
    r".*\.costco\.com$",
    r".*\.samsclub\.com$",
    r".*\.zappos\.com$",
    r".*\.nordstrom\.com$",
    r".*\.macys\.com$",
    r".*\.kohls\.com$",
    r".*\.jcpenney\.com$",
    r".*\.ikea\.com$",
    r".*\.rakuten\.com$",
    r".*\.mercadolibre\.com$",
    r".*\.flipkart\.com$",
    r".*\.temu\.com$",
    r".*\.shein\.com$",
]

# Major mainstream news outlets
NEWS_PATTERNS = [
    r".*\.cnn\.com$",
    r".*\.nytimes\.com$",
    r".*\.washingtonpost\.com$",
    r".*\.bbc\.com$",
    r".*\.bbc\.co\.uk$",
    r".*\.foxnews\.com$",
    r".*\.nbcnews\.com$",
    r".*\.cbsnews\.com$",
    r".*\.abcnews\.go\.com$",
    r".*\.msnbc\.com$",
    r".*\.npr\.org$",
    r".*\.pbs\.org$",
    r".*\.reuters\.com$",
    r".*\.apnews\.com$",
    r".*\.usatoday\.com$",
    r".*\.wsj\.com$",
    r".*\.bloomberg\.com$",
    r".*\.theguardian\.com$",
    r".*\.huffpost\.com$",
    r".*\.huffingtonpost\.com$",
    r".*\.buzzfeed\.com$",
    r".*\.vice\.com$",
    r".*\.vox\.com$",
    r".*\.politico\.com$",
    r".*\.axios\.com$",
    r".*\.thehill\.com$",
    r".*\.dailymail\.co\.uk$",
    r".*\.nypost\.com$",
    r".*\.latimes\.com$",
    r".*\.chicagotribune\.com$",
    r".*\.newsweek\.com$",
    r".*\.time\.com$",
    r".*\.fortune\.com$",
    r".*\.forbes\.com$",
    r".*\.cnbc\.com$",
    r".*\.businessinsider\.com$",
    r".*\.insider\.com$",
    r".*\.economist\.com$",
    r".*\.ft\.com$",
    r".*\.aljazeera\.com$",
    r".*\.rt\.com$",
    r".*\.sputniknews\.com$",
    r".*\.breitbart\.com$",
    r".*\.infowars\.com$",
    r".*\.thedailybeast\.com$",
    r".*\.theatlantic\.com$",
    r".*\.newyorker\.com$",
    r".*\.slate\.com$",
    r".*\.salon\.com$",
    r".*\.motherjones\.com$",
    r".*\.thenation\.com$",
    r".*\.nationalreview\.com$",
    r".*\.spectator\.org$",
]

# Known spam/SEO/scraper patterns
SPAM_PATTERNS = [
    r".*\.blogspot\.com$",
    r".*\.wordpress\.com$",  # Free WordPress sites (paid domains are fine)
    r".*\.weebly\.com$",
    r".*\.wix\.com$",
    r".*\.medium\.com$",
    r".*\.substack\.com$",
    r".*\.hubpages\.com$",
    r".*\.squidoo\.com$",
    r".*\.ezinearticles\.com$",
    r".*\.articlesbase\.com$",
    r".*\.goarticles\.com$",
    r".*\d{5,}.*",  # Domains with lots of numbers (often spam)
]

# Adult content patterns
ADULT_PATTERNS = [
    r".*\.pornhub\.com$",
    r".*\.xvideos\.com$",
    r".*\.xnxx\.com$",
    r".*\.xhamster\.com$",
    r".*\.redtube\.com$",
    r".*\.youporn\.com$",
    r".*\.tube8\.com$",
    r".*\.spankbang\.com$",
    r".*\.onlyfans\.com$",
    r".*\.chaturbate\.com$",
    r".*\.livejasmin\.com$",
    r".*porn.*",
    r".*xxx.*",
    r".*\.adult\..*",
]

# CDN and infrastructure (should be ignored, not crawled)
INFRASTRUCTURE_PATTERNS = [
    r".*\.cloudflare\.com$",
    r".*\.akamai\..*$",
    r".*\.fastly\..*$",
    r".*\.cloudfront\.net$",
    r".*\.googleapis\.com$",
    r".*\.gstatic\.com$",
    r".*\.googleusercontent\.com$",
    r".*\.fbcdn\.net$",
    r".*\.twimg\.com$",
    r".*\.cdn\..*$",
    r".*\.static\..*$",
]


def compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    """Compile regex patterns for efficiency."""
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# Pre-compiled patterns for performance
COMPILED_RULES: dict[HostCategory, list[re.Pattern]] = {
    HostCategory.BAN_MEDIA: compile_patterns(MEDIA_PATTERNS),
    HostCategory.BAN_SOCIAL: compile_patterns(SOCIAL_PATTERNS),
    HostCategory.BAN_ECOM: compile_patterns(ECOM_PATTERNS),
    HostCategory.BAN_NEWS: compile_patterns(NEWS_PATTERNS),
    HostCategory.BAN_SPAM: compile_patterns(SPAM_PATTERNS + INFRASTRUCTURE_PATTERNS),
    HostCategory.BAN_ADULT: compile_patterns(ADULT_PATTERNS),
}


def classify_by_rules(host: str) -> Optional[ClassificationResult]:
    """
    Attempt to classify a host using hardcoded rules.

    Returns a ClassificationResult if a rule matches, None otherwise.
    """
    host_lower = host.lower()

    # Remove www. prefix for matching
    if host_lower.startswith("www."):
        host_lower = host_lower[4:]

    for category, patterns in COMPILED_RULES.items():
        for pattern in patterns:
            if pattern.match(host_lower):
                return ClassificationResult(
                    host=host,
                    category=category,
                    confidence=1.0,  # Hardcoded rules have full confidence
                    reason=f"Matched hardcoded rule: {pattern.pattern}",
                    source="hardcoded",
                )

    return None


def is_likely_good_host(host: str) -> bool:
    """
    Quick check for hosts that are likely good (educational, gov, org).
    These should still go through LLM but with a bias toward KEEP.
    """
    host_lower = host.lower()
    good_tlds = [".edu", ".gov", ".mil", ".ac.uk", ".edu.au", ".ac.jp"]
    return any(host_lower.endswith(tld) for tld in good_tlds)


def get_host_hints(host: str) -> dict:
    """
    Get hints about a host that can be passed to the LLM.
    """
    host_lower = host.lower()
    hints = {
        "is_educational": any(host_lower.endswith(x) for x in [".edu", ".ac.uk", ".edu.au"]),
        "is_government": any(host_lower.endswith(x) for x in [".gov", ".mil"]),
        "is_organization": host_lower.endswith(".org"),
        "has_numbers": any(c.isdigit() for c in host),
        "is_subdomain_heavy": host.count(".") > 2,
    }
    return hints
