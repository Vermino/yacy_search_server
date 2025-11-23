# YaCy Seed Collector & LLM Janitor

A set of tools for curating your YaCy search index:

1. **Seed Collector** - Add URLs to your seed list while browsing
2. **LLM Janitor** - Automatically classify and filter hosts in your index
3. **Janitor API** - HTTP endpoints for manual review and management

## Quick Start

```bash
# 1. Copy and configure environment
cp tools/env.example .env
# Edit .env with your settings (especially LLM_API_KEY)

# 2. Start the stack
docker-compose -f docker-compose.janitor.yml up -d

# 3. Access services
# YaCy:           http://localhost:8090
# Seed Collector: http://localhost:8091
# Janitor API:    http://localhost:8092
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│  YaCy           │    │  Seed Collector  │    │  LLM Janitor      │
│  (port 8090)    │◄───│  (port 8091)     │    │  (background)     │
│                 │    │                  │    │                   │
│  - Search Index │    │  - POST /seed    │◄───│  - Host Scanner   │
│  - Blacklists   │◄───│  - POST /share   │    │  - LLM Classifier │
│  - Crawling     │    │  - PWA Support   │    │  - Index Cleaner  │
└─────────────────┘    └──────────────────┘    └───────────────────┘
         ▲                      │                        │
         │              ┌───────┴───────┐                │
         │              │ Janitor API   │◄───────────────┘
         │              │ (port 8092)   │
         │              │ - Review Queue│
         │              │ - Host Lists  │
         │              │ - Seed Gen    │
         │              └───────────────┘
         │                      │
         └──────────────────────┼────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Shared Data Volume   │
                    │  - queued_seeds.jsonl │
                    │  - keep_hosts.txt     │
                    │  - ban_hosts.txt      │
                    │  - curated_seeds.txt  │
                    │  - url_mustmatch.regex│
                    └───────────────────────┘
```

## Seed Collector

### Browser Integration

**Bookmarklet** (drag to bookmarks bar):

Visit http://localhost:8091 to get a ready-to-use bookmarklet, or http://localhost:8091/bookmarklet for the interactive setup page.

**PWA / Mobile Share Target**:

The seed collector is a Progressive Web App. On mobile:
1. Visit the collector URL in your browser
2. Add to Home Screen
3. Use the Share menu from any app to send URLs directly

### API

```bash
# Add a seed
curl -X POST http://localhost:8091/seed \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "tags": ["tech", "tutorial"]}'

# View queue
curl http://localhost:8091/queue

# Get statistics
curl http://localhost:8091/queue/stats

# Get pending hosts
curl http://localhost:8091/hosts
```

## LLM Janitor

### Classification Categories

| Category | Description |
|----------|-------------|
| `keep` | Good content - technical, educational, homesteading |
| `ban_media` | Video/audio platforms (YouTube, TikTok, Spotify) |
| `ban_social` | Social media (Facebook, Twitter, Reddit) |
| `ban_ecom` | E-commerce (Amazon, eBay, Walmart) |
| `ban_news` | Mainstream news (CNN, NYT, BBC) |
| `ban_spam` | SEO spam, content farms |
| `ban_adult` | Adult content |
| `unsure` | Needs manual review |

### Hardcoded Rules

Common domains are classified instantly without LLM calls:
- All major social platforms
- All major video/streaming platforms
- All major e-commerce sites
- All major news outlets

This saves API costs and speeds up processing.

### Actions on Classification

When a host is classified:
- **KEEP**: Added to `keep_hosts.txt`
- **BAN**: Added to `ban_hosts.txt`, added to YaCy blacklist, deleted from YaCy index
- **UNSURE**: Added to `manual_review.jsonl` for human review

## Janitor API

The Janitor API (port 8092) provides HTTP endpoints for management:

### Review Queue

```bash
# Get items pending review
curl http://localhost:8092/review

# Approve a host (add to keep list)
curl -X POST http://localhost:8092/review/decide \
  -H "Content-Type: application/json" \
  -d '{"host": "example.com", "action": "keep"}'

# Ban a host (add to ban list + delete from index)
curl -X POST http://localhost:8092/review/decide \
  -H "Content-Type: application/json" \
  -d '{"host": "spam.com", "action": "ban"}'

# Skip (remove from review without deciding)
curl -X POST http://localhost:8092/review/decide \
  -H "Content-Type: application/json" \
  -d '{"host": "unknown.com", "action": "skip"}'
```

### Host List Management

```bash
# View keep/ban lists
curl http://localhost:8092/hosts/keep
curl http://localhost:8092/hosts/ban

# Manually add hosts
curl -X POST http://localhost:8092/hosts/keep/goodsite.com
curl -X POST http://localhost:8092/hosts/ban/badsite.com

# Remove hosts
curl -X DELETE http://localhost:8092/hosts/keep/goodsite.com
curl -X DELETE http://localhost:8092/hosts/ban/badsite.com
```

### Seed & Regex Generation

```bash
# Generate curated_seeds.txt from keep_hosts.txt
curl -X POST http://localhost:8092/generate/seeds

# Generate URL regex patterns for YaCy crawler
curl -X POST http://localhost:8092/generate/regex

# Generate all (seeds + regex)
curl -X POST http://localhost:8092/generate/all
```

## Generated Files

The system generates these files for use with YaCy:

| File | Purpose |
|------|---------|
| `curated_seeds.txt` | URLs to crawl (from keep_hosts.txt) |
| `url_mustmatch.regex` | Regex for crawler URL whitelist |
| `url_mustnotmatch.regex` | Regex for crawler URL blacklist |

Copy the regex to YaCy's crawler settings:
- **Mustmatch**: Only crawl URLs matching this pattern
- **Mustnotmatch**: Never crawl URLs matching this pattern

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YACY_URL` | `http://yacy:8090` | YaCy instance URL |
| `YACY_ADMIN_PASSWORD` | `yacy` | YaCy admin password |
| `YACY_BLACKLIST_NAME` | `blacklist.black` | YaCy blacklist file |
| `LLM_API_KEY` | - | OpenAI API key |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model to use |
| `LLM_BASE_URL` | - | Custom LLM endpoint |
| `HOST_SCAN_INTERVAL` | `60` | Minutes between host scans |
| `KEEP_THRESHOLD` | `0.7` | Confidence to auto-keep |
| `BAN_THRESHOLD` | `0.8` | Confidence to auto-ban |
| `PUBLIC_URL` | `http://localhost:8091` | Public URL for bookmarklet |

### Using Local LLMs

For Ollama:
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3
LLM_API_KEY=ollama  # Any non-empty string
```

## Data Files

All data is stored in the `janitor_data` Docker volume:

| File | Purpose |
|------|---------|
| `queued_seeds.jsonl` | Incoming URLs from collector |
| `keep_hosts.txt` | Approved hosts |
| `ban_hosts.txt` | Banned hosts |
| `manual_review.jsonl` | Hosts needing review |
| `classification_cache.json` | LLM decision cache |
| `curated_seeds.txt` | Generated seed URLs |
| `url_mustmatch.regex` | Generated whitelist regex |
| `url_mustnotmatch.regex` | Generated blacklist regex |

## Workflow

1. **While browsing**: Click bookmarklet or use mobile share to send URLs
2. **Every 5 minutes**: Janitor processes new seeds from queue
3. **Every hour**: Janitor scans YaCy index for new hosts
4. **Classification**:
   - Try hardcoded rules first (instant, free)
   - Fall back to LLM for unknown hosts
5. **Actions**:
   - High-confidence KEEP → add to keep_hosts.txt
   - High-confidence BAN → add to ban_hosts.txt + YaCy blacklist + delete from index
   - Low confidence → add to manual_review.jsonl
6. **Manual Review**: Use Janitor API to approve/reject uncertain hosts
7. **Generate Seeds**: Create crawler seed files and regex patterns

## Development

```bash
# Run seed collector locally
cd tools/seed-collector
pip install -r requirements.txt
python main.py

# Run janitor locally (single scan)
cd tools/yacy-janitor
pip install -r requirements.txt
python main.py --once

# Run janitor API locally
cd tools/yacy-janitor
python api.py

# Generate seeds manually
cd tools/yacy-janitor
python seed_generator.py
```

## Troubleshooting

### Janitor can't connect to YaCy
- Check YaCy is running: `curl http://localhost:8090`
- Verify admin password in `.env`

### No LLM classifications happening
- Verify `LLM_API_KEY` is set
- Check logs: `docker-compose logs janitor`

### Seeds not being processed
- Check queue: `curl http://localhost:8091/queue`
- Verify shared volume is mounted correctly

### PWA not installing on mobile
- Ensure HTTPS is configured (required for PWA)
- Check that manifest.json is served correctly
