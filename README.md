# News Scraping & AI Summarization System

Automated pipeline that runs daily at 9:00 AM: fetch news from configurable RSS sources, scrape full article content, generate AI summaries with OpenAI, and store everything in Supabase.

## System Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  RSS / Feeds    │────▶│  Scraper         │────▶│  Full content   │
│  (BBC, CNN,…)   │     │  fetch_sources   │     │  scrape_article │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                           │
                                                           ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Supabase       │◀────│  Article         │◀────│  AI Summarize   │
│  (articles,     │     │  Repository       │     │  (OpenAI)       │
│   sources)      │     │  upsert          │     └─────────────────┘
└─────────────────┘     └──────────────────┘
         ▲
         │
┌────────┴────────┐
│  Scheduler      │  Cron / GitHub Actions / run_scheduler.py
│  9:00 AM daily  │
└─────────────────┘
```

- **Scraper**: Fetches feed entries (title, URL, source, published_at) from RSS; then fetches full article HTML and extracts text (newspaper3k + BeautifulSoup fallback).
- **AI**: OpenAI generates a short, factual summary (3–5 bullets or paragraph).
- **DB**: Supabase stores sources and articles; upsert by `article_url` for idempotency; optional skip of already-seen URLs to save work.
- **Scheduler**: Run once via cron or GitHub Actions, or use in-process `run_scheduler.py` for daily 9 AM.

## Prerequisites

- Python 3.10+
- Supabase project
- OpenAI API key

## Environment Variables

Copy `.env.example` to `.env` and set:

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Service role key (server-side only) |
| `OPENAI_API_KEY` | OpenAI API key for summarization |
| `DAILY_RUN_HOUR` | Hour for daily run (24h, default 9) |
| `DAILY_RUN_MINUTE` | Minute (default 0) |
| `SCRAPER_DELAY_SECONDS` | Delay between requests (default 2) |
| `LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR |

## Database Setup

1. In Supabase: **SQL Editor** → New query.
2. Paste and run the contents of `schema/schema.sql`.
3. This creates `sources` and `articles` and seeds default RSS sources (Google News, BBC, Reuters, CNN).

## Sample Run Instructions

### One-off run (e.g. for cron or CI)

```bash
# From project root
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys

python -m src.main
```

### In-process scheduler (runs daily at 9:00 AM)

```bash
python run_scheduler.py
```

### View news in the dashboard

```bash
pip install -r requirements.txt   # includes Flask
python run_dashboard.py
```

Then open **http://127.0.0.1:5000** in your browser. The dashboard shows the latest scraped articles (title, AI summary, source, date, link to full article). Use the tabs to filter by category: **All**, News, Sport, Business, Technology, Health, **Pharma** (Fierce Pharma, ET Pharma).

### Windows Task Scheduler / Linux cron (9:00 AM daily)

- **Cron (Linux/macOS):**  
  `0 9 * * * cd /path/to/news\ scrapper && python -m src.main`
- **Windows:** Create a daily task at 9:00 AM that runs `python -m src.main` with working directory set to the project.

### GitHub Actions

1. In the repo: **Settings** → **Secrets and variables** → **Actions**.
2. Add secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`.
3. The workflow in `.github/workflows/daily-news-job.yml` runs at 9:00 AM UTC; use `workflow_dispatch` to trigger manually.

## Constraints & Practices

- **robots.txt**: Respect it; use reasonable delays (`SCRAPER_DELAY_SECONDS`).
- **Errors**: One bad article or feed does not stop the job; failures are logged.
- **Idempotency**: Re-running the job is safe; duplicates are avoided by `article_url` (and optional URL skip).
- **Summaries**: Prompt is tuned for neutral, factual output only.

## Project Structure

```
/src
  /scraper    fetch_sources.py, scrape_article.py
  /ai         summarize.py
  /db         supabase_client.py, article_repository.py
  /scheduler  daily_job.py
  config.py, main.py
/supabase    schema.sql
run_scheduler.py   # In-process daily scheduler
```

## License

MIT.
