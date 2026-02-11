"""
News dashboard: web UI to view scraped articles from Supabase.
Run: python run_dashboard.py  →  http://127.0.0.1:5000
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, abort
from src.db.article_repository import ArticleRepository

app = Flask(__name__)

# Fixed tab order: All (no filter), then News, Sport, Business, Technology, Health, Pharma
TAB_OPTIONS = ["All", "News", "Sport", "Business", "Technology", "Health", "Pharma"]


def _time_ago(dt_str: str | None) -> str:
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        mins = int(delta.total_seconds() / 60)
        if mins < 1:
            return "Just now"
        if mins < 60:
            return f"{mins} min ago"
        hrs = mins // 60
        if hrs == 1:
            return "1 hr ago"
        if hrs < 24:
            return f"{hrs} hrs ago"
        days = hrs // 24
        return "1 day ago" if days == 1 else f"{days} days ago"
    except Exception:
        return dt_str[:10] if dt_str else ""


@app.route("/")
def index():
    category_param = (request.args.get("category") or "").strip() or None
    # "All" as explicit param same as no filter
    if category_param and category_param.lower() == "all":
        category_param = None
    try:
        repo = ArticleRepository()
        articles = repo.get_articles(
            limit=100, order_by="published_at", desc=True, category=category_param
        )
        for a in articles:
            a["time_ago"] = _time_ago(a.get("published_at") or a.get("created_at"))
            summary = (a.get("summary") or "").strip()
            full = (a.get("full_content") or "").strip()
            if summary:
                a["display_summary"] = summary
            elif full:
                a["display_summary"] = (full[:300] + "…") if len(full) > 300 else full
            else:
                a["display_summary"] = "Open the article to read more."
    except Exception as e:
        articles = []
        app.logger.exception("Failed to load: %s", e)
    return render_template(
        "dashboard.html",
        articles=articles,
        tab_options=TAB_OPTIONS,
        current_category=category_param,
    )


@app.route("/article/<article_id>")
def article_detail(article_id: str):
    """Detail view: show full article on our site; title links to original URL."""
    repo = ArticleRepository()
    article = repo.get_article_by_id(article_id)
    if not article:
        abort(404)

    article["time_ago"] = _time_ago(article.get("published_at") or article.get("created_at"))
    summary = (article.get("summary") or "").strip()
    full = (article.get("full_content") or "").strip()
    if not full and summary:
        full = summary
    article["display_full"] = full

    return render_template("article_detail.html", article=article)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
