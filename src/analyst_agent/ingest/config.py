import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache
def admin_db_url() -> str:
    url = os.getenv("ANALYST_DB_ADMIN_URL")
    if not url:
        raise RuntimeError("ANALYST_DB_ADMIN_URL is not set (see .env.example)")
    return url


@lru_cache
def sec_user_agent() -> str:
    ua = os.getenv("SEC_USER_AGENT")
    if not ua or "your@email" in ua:
        raise RuntimeError(
            "SEC_USER_AGENT must be set to 'app-name your@email.com'. "
            "EDGAR returns 403 without a contact address."
        )
    return ua
