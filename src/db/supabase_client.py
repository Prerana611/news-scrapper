"""
Supabase client singleton. Uses service role key for server-side operations.
"""
import logging
from typing import Optional

from supabase import create_client, Client

from src.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


def _mask_key(key: str) -> str:
    """Safe hint for logs: first 10 chars + ... + last 4."""
    if not key or len(key) < 20:
        return "(too short or empty)"
    return f"{key[:10]}...{key[-4:]}"


def get_supabase_client() -> Client:
    """Return a single Supabase client instance."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
            )
        # Catch placeholder or obviously wrong key
        if "your-service-role-key" in SUPABASE_SERVICE_KEY.lower() or len(SUPABASE_SERVICE_KEY) < 40:
            raise ValueError(
                "SUPABASE_SERVICE_KEY looks invalid. Use the service_role (Legacy tab) or "
                "a Secret key from Supabase Dashboard → Project → Settings → API Keys."
            )
        # Accept both: legacy JWT (eyJ...) and new secret key (sb_secret_...)
        valid_prefix = SUPABASE_SERVICE_KEY.startswith("eyJ") or SUPABASE_SERVICE_KEY.startswith("sb_secret_")
        if not valid_prefix:
            raise ValueError(
                "SUPABASE_SERVICE_KEY should be either: (1) Legacy service_role JWT (starts with eyJ) "
                "from tab 'Legacy anon, service_role API keys', or (2) new Secret key (starts with sb_secret_). "
                "Do not use the publishable/anon key."
            )
        logger.debug("Supabase URL: %s | Key: %s", SUPABASE_URL, _mask_key(SUPABASE_SERVICE_KEY))
        try:
            _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        except Exception as e:
            msg = str(e).lower()
            if "invalid" in msg and "key" in msg:
                raise ValueError(
                    "Supabase rejected the API key. Check: (1) Key is from the same project as SUPABASE_URL "
                    "(lldpbdovpktfygdabqfk). (2) You used the secret/service_role key, not publishable/anon. "
                    "(3) No extra spaces or line breaks in .env. (4) Try the Legacy tab → service_role (Reveal → Copy)."
                ) from e
            raise
        logger.info("Supabase client initialized")
    return _client
