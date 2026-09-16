from analyst_agent.config import get_settings


def admin_db_url() -> str:
    settings = get_settings()
    settings.require("analyst_db_admin_url")
    return settings.analyst_db_admin_url


def sec_user_agent() -> str:
    settings = get_settings()
    settings.require("sec_user_agent")
    if "your@email" in settings.sec_user_agent:
        raise RuntimeError(
            "SEC_USER_AGENT still holds the placeholder address. EDGAR returns 403 "
            "without a real contact address."
        )
    return settings.sec_user_agent
