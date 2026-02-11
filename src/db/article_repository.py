"""
Article and source repository: insert/upsert and fetch for dashboard.
"""
import logging
from typing import Any, Optional

from src.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def _row_to_article(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "source_id": row.get("source_id"),
        "source_name": row.get("source_name"),
        "title": row.get("title"),
        "article_url": row.get("article_url"),
        "full_content": row.get("full_content"),
        "summary": row.get("summary"),
        "published_at": row.get("published_at"),
        "content_hash": row.get("content_hash"),
        "created_at": row.get("created_at"),
    }


class ArticleRepository:
    def __init__(self):
        self.client = get_supabase_client()

    def upsert_article(
        self,
        *,
        source_id: Optional[str],
        source_name: str,
        title: str,
        article_url: str,
        full_content: Optional[str],
        summary: Optional[str],
        published_at: Optional[str],
        content_hash: str,
        image_url: Optional[str] = None,
    ) -> dict[str, Any] | None:
        payload = {
            "source_id": source_id,
            "source_name": source_name,
            "title": title,
            "article_url": article_url,
            "full_content": full_content or "",
            "summary": summary or "",
            "published_at": published_at,
            "content_hash": content_hash,
            "image_url": image_url or "",
        }
        try:
            result = (
                self.client.table("articles")
                .upsert(payload, on_conflict="article_url", ignore_duplicates=False)
                .execute()
            )
            if result.data and len(result.data) > 0:
                return _row_to_article(result.data[0])
            return None
        except Exception as e:
            logger.exception("Upsert article failed: %s", e)
            return None

    def get_sources(self, active_only: bool = True) -> list[dict[str, Any]]:
        try:
            q = self.client.table("sources").select("*")
            if active_only:
                q = q.eq("is_active", True)
            result = q.order("name").execute()
            return result.data or []
        except Exception as e:
            logger.exception("Get sources failed: %s", e)
            return []

    def get_categories(self) -> list[str]:
        try:
            sources = self.get_sources(active_only=True)
            categories = sorted({(s.get("category") or "General") for s in sources})
            return categories
        except Exception as e:
            logger.exception("Get categories failed: %s", e)
            return []

    def get_source_names_by_category(self, category: str) -> list[str]:
        try:
            q = self.client.table("sources").select("name").eq("is_active", True)
            # "News" tab shows general news: sources with category News, General, or World
            if category.strip().lower() == "news":
                q = q.in_("category", ["News", "General", "World"])
            else:
                q = q.eq("category", category.strip())
            result = q.execute()
            return [r["name"] for r in (result.data or []) if r.get("name")]
        except Exception as e:
            logger.exception("Get source names by category failed: %s", e)
            return []

    def get_articles(
        self,
        limit: int = 50,
        order_by: str = "published_at",
        desc: bool = True,
        category: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        try:
            col = "published_at" if order_by == "published_at" else "created_at"
            q = (
                self.client.table("articles")
                .select("id, title, summary, full_content, source_name, article_url, published_at, created_at, image_url")
                .order(col, desc=desc)
                .limit(limit)
            )
            if category and category.strip() and category.strip().lower() != "all":
                source_names = self.get_source_names_by_category(category.strip())
                if not source_names:
                    return []
                q = q.in_("source_name", source_names)
            result = q.execute()
            return [dict(row) for row in (result.data or [])]
        except Exception as e:
            logger.exception("Get articles failed: %s", e)
            return []

    def article_exists_by_url(self, article_url: str) -> bool:
        try:
            result = (
                self.client.table("articles")
                .select("id")
                .eq("article_url", article_url)
                .limit(1)
                .execute()
            )
            return bool(result.data and len(result.data) > 0)
        except Exception as e:
            logger.warning("article_exists_by_url failed: %s", e)
            return False
