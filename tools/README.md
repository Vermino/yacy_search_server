# YaCy Seed Collector & LLM Janitor

A set of tools for curating your YaCy search index:

1. **Seed Collector** - Add URLs to your seed list while browsing
2. **LLM Janitor** - Automatically classify and filter hosts in your index

## Quick Start

```bash
# 1. Copy and configure environment
cp tools/env.example .env
# Edit .env with your settings (especially LLM_API_KEY)

# 2. Start the stack
docker-compose -f docker-compose.janitor.yml up -d

# 3. Access services
# YaCy:          http://localhost:8090
# Seed Collector: http://localhost:8091
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│  YaCy           │    │  Seed Collector  │    │  LLM Janitor      │
│  (port 8090)    │◄───│  (port 8091)     │    │  (background)     │
│                 │    │                  │    │                   │
│  - Search Index │    │  - POST /seed    │◄───│  - Host Scanner   │
│  - Blacklists   │◄───│  - GET /queue    │    │  - LLM Classifier │
│  - Crawling     │    │                  │    │  - Index Cleaner  │
└─────────────────┘    └──────────────────┘    └───────────────────┘
         ▲                      │                        │
         └──────────────────────┼────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Shared Data Volume   │
                    │  - queued_seeds.jsonl │
                    │  - keep_hosts.txt     │
                    │  - ban_hosts.txt      │
                    │  - manual_review.jsonl│
                    └───────────────────────┘
```

## Seed Collector

### Browser Integration

**Bookmarklet** (drag to bookmarks bar):

Visit http://localhost:8091 to get a ready-to-use bookmarklet.

Or create one manually:
```javascript
javascript:(function(){fetch('http://localhost:8091/seed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:location.href,title:document.title})}).then(r=>r.json()).then(d=>alert('Added: '+d.message)).catch(e=>alert('Error: '+e))})();
```

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

### Manual Review

Hosts that can't be confidently classified are added to:
```
/data/manual_review.jsonl
```

Review and move them to keep/ban lists manually.

### Running Manually

```bash
# Single scan (useful for testing)
docker-compose -f docker-compose.janitor.yml exec janitor python main.py --once

# View logs
docker-compose -f docker-compose.janitor.yml logs -f janitor
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YACY_URL` | `http://yacy:8090` | YaCy instance URL |
| `YACY_ADMIN_PASSWORD` | `yacy` | YaCy admin password |
| `LLM_API_KEY` | - | OpenAI API key |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model to use |
| `LLM_BASE_URL` | - | Custom LLM endpoint |
| `HOST_SCAN_INTERVAL` | `60` | Minutes between host scans |
| `KEEP_THRESHOLD` | `0.7` | Confidence to auto-keep |
| `BAN_THRESHOLD` | `0.8` | Confidence to auto-ban |

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

## Workflow

1. **While browsing**: Click bookmarklet to send URLs to collector
2. **Every 5 minutes**: Janitor processes new seeds
3. **Every hour**: Janitor scans YaCy index for new hosts
4. **Classification**:
   - Try hardcoded rules first (instant, free)
   - Fall back to LLM for unknown hosts
5. **Actions**:
   - High-confidence KEEP → add to keep_hosts.txt
   - High-confidence BAN → add to ban_hosts.txt + delete from YaCy
   - Low confidence → add to manual_review.jsonl

## Development

```bash
# Run seed collector locally
cd tools/seed-collector
pip install -r requirements.txt
python main.py

# Run janitor locally
cd tools/yacy-janitor
pip install -r requirements.txt
python main.py --once
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
