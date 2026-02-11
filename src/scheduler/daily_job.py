"""
Daily job: fetch feeds -> scrape full content -> summarize -> upsert to Supabase.
Idempotent: safe to re-run; duplicates are avoided by article_url.
"""
import logging
from typing import Any

from src.db.article_repository import ArticleRepository
from src.scraper.scrape_article import scrape_article_content, content_hash
from src.scraper.bbc_scraper import scrape_bbc_article_page
from src.scraper.google_news_scraper import fetch_google_news_full_content, resolve_google_news_url
from src.scraper.site_scraper import collect_entries_for_sources
from src.ai.summarize import summarize_with_openai

logger = logging.getLogger(__name__)


def run_daily_job(skip_existing_urls: bool = True, max_articles_per_source: int = 25) -> None:
    """
    Run the full pipeline: sources -> feeds -> scrape -> summarize -> DB.
    One bad article or source does not crash the job.
    """
    repo = ArticleRepository()
    sources = repo.get_sources(active_only=True)
    if not sources:
        logger.warning("No active sources found; add sources in Supabase or run schema seed")
        return

    # Use unified site_scraper module to discover article entries for all sources.
    # Pass limit per source to collect_entries_for_sources
    entries = collect_entries_for_sources(sources, limit_per_source=max_articles_per_source)

    processed = 0
    # Process all collected entries (they are already limited per source)
    for i, entry in enumerate(entries):

        url = entry.get("article_url")
        title = entry.get("title") or ""
        entry_source = entry.get("source") or "Unknown"
        published_at = entry.get("published_at")
        source_id = None
        source_name = entry_source
        # Match source by name (exact match)
        for s in sources:
            if s.get("name") == entry_source:
                source_id = s.get("id")
                source_name = s.get("name")
                break

        if not url:
            continue

        try:
            if skip_existing_urls and repo.article_exists_by_url(url):
                logger.debug("Skip existing URL: %s", url[:80])
                continue

            # For BBC articles, use BBC-specific scraper for better content/image extraction
            # For Google News, resolve URL and fetch from publisher
            image_url = entry.get("image_url")
            resolved_url = url  # Default to original URL
            
            if url.startswith("https://www.bbc.com/") or url.startswith("http://www.bbc.com/"):
                full_content, page_image, page_published = scrape_bbc_article_page(url)
                if page_image:
                    image_url = page_image
                if page_published and not published_at:
                    published_at = page_published
                if not full_content:
                    # Fallback to generic scraper if BBC scraper didn't get content
                    full_content, image_url_fallback, hash_value = scrape_article_content(url)
                    if image_url_fallback and not image_url:
                        image_url = image_url_fallback
                else:
                    # Use content hash from BBC content
                    hash_value = content_hash(full_content) if full_content else content_hash(url)
            elif entry.get("is_google_news_url") or "news.google.com" in url or "news.google.com" in (entry_source.lower()):
                # Google News: resolve URL and fetch full content from publisher
                full_content, image_url_fallback, resolved_url = fetch_google_news_full_content(url)
                if image_url_fallback and not image_url:
                    image_url = image_url_fallback
                hash_value = content_hash(full_content) if full_content else content_hash(resolved_url or url)
                # Store resolved URL for better user experience
                if resolved_url and resolved_url != url:
                    url = resolved_url
            else:
                # Non-BBC: use generic scraper
                full_content, image_url_fallback, hash_value = scrape_article_content(url)
                if image_url_fallback and not image_url:
                    image_url = image_url_fallback

            # If we have no content, still store the record with empty content and hash from URL
            summary = summarize_with_openai(title, full_content) if full_content else None

            row = repo.upsert_article(
                source_id=source_id,
                source_name=source_name,
                title=title,
                article_url=url,
                full_content=full_content,
                summary=summary,
                published_at=published_at,
                content_hash=hash_value,
                image_url=image_url,
            )
            if row:
                processed += 1
                logger.info("Upserted [%d]: %s", processed, title[:60])
        except Exception as e:
            logger.exception("Failed to process article %s: %s", url, e)
            # Continue with next article

    logger.info("Daily job finished; processed %d articles", processed)
