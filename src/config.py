"""
Central configuration loaded from environment variables.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Always load .env from project root so it works regardless of cwd; override existing env
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

def get_env(key: str, default: str | None = None) -> str | None:
    """Get required or optional env var (stripped of surrounding whitespace)."""
    val = os.environ.get(key, default)
    if not isinstance(val, str):
        return val
    return val.strip().replace("\r", "")


# Supabase: strip whitespace, BOM, trailing slash on URL
_raw_url = (get_env("SUPABASE_URL", "") or "").strip().replace("\r", "")
SUPABASE_URL = _raw_url.rstrip("/") if _raw_url else ""
_raw_key = (get_env("SUPABASE_SERVICE_KEY", "") or "").strip().replace("\r", "")
SUPABASE_SERVICE_KEY = _raw_key

# OpenAI
OPENAI_API_KEY = get_env("OPENAI_API_KEY", "")

# Scheduler
DAILY_RUN_HOUR = int(get_env("DAILY_RUN_HOUR", "9"))
DAILY_RUN_MINUTE = int(get_env("DAILY_RUN_MINUTE", "0"))

# Scraper
SCRAPER_DELAY_SECONDS = float(get_env("SCRAPER_DELAY_SECONDS", "2"))

# Logging
# Logging
LOG_LEVEL = get_env("LOG_LEVEL", "INFO")

# Shared HTTP Headers (Browser-like to avoid blocking)
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
