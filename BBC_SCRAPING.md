# BBC News Full Web Scraping

## Overview

The system now supports **full web scraping** from BBC News pages (https://www.bbc.com/) instead of just RSS feeds. This provides:

- **Richer content**: Full article text extracted from BBC article pages
- **Real images**: Article thumbnails extracted from BBC pages (og:image, BBC image tags)
- **Better metadata**: Published dates extracted from article pages
- **More articles**: Scrapes directly from section pages (Business, Technology, Health, Sport, News)

## How It Works

### 1. **BBC Section Scraping** (`src/scraper/bbc_scraper.py`)

For BBC sources (identified by name starting with "BBC" and category in Business/Technology/Health/Sport/News), the scraper:

- Visits the BBC section page (e.g., `https://www.bbc.com/news/business`)
- Extracts article links, titles, and thumbnail images from the listing page
- Returns article entries with `title`, `article_url`, `image_url`, `source`, `published_at`

### 2. **BBC Article Page Scraping**

For each BBC article URL, the scraper:

- Fetches the full article page
- Extracts main content from `<article>` or `<main>` with `data-component="text-block"`
- Extracts image URL from `og:image` meta tag or BBC image tags
- Extracts published date from `<time>` elements or meta tags

### 3. **Database Schema**

Run this SQL in Supabase to add `image_url` column:

```sql
-- Run: schema/add_image_url.sql
ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_url TEXT;
```

### 4. **Daily Job**

The `run_daily_job()` function:

- **BBC sources**: Uses `scrape_bbc_section()` to get articles from section pages, then `scrape_bbc_article_page()` for full content/images
- **Other sources**: Uses RSS feeds (`fetch_all_feeds`) as before

## Setup

1. **Add image_url column** (if not already done):
   ```sql
   -- Run in Supabase SQL Editor
   ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_url TEXT;
   ```

2. **Ensure BBC sources have correct categories**:
   - Run `schema/add_categories.sql` to set categories: Business, Technology, Health, Sport, News

3. **Run the scraper**:
   ```bash
   python -m src.main
   ```

## Result

- **Dashboard shows real BBC article images** (not placeholders)
- **Full article content** scraped from BBC pages
- **Better summaries** from richer content
- **More articles** from direct page scraping vs RSS limits

## Notes

- BBC scraping respects rate limits (`SCRAPER_DELAY_SECONDS`)
- Falls back to generic scraper if BBC-specific extraction fails
- Images are stored as URLs (not base64) to keep DB size manageable
- Non-BBC sources continue using RSS feeds (works as before)
