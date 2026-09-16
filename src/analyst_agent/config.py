from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    analyst_db_url: str = Field(
        default="",
        description="Read-only analyst_ro connection used by the MCP server",
    )
    analyst_db_admin_url: str = Field(
        default="",
        description="Owner connection used by the ingest pipeline only",
    )

    sec_user_agent: str = Field(
        default="",
        description="EDGAR requires a contact address: 'app-name your@email.com'",
    )

    aws_region: str = "us-east-1"
    aws_profile: str | None = Field(
        default=None,
        description="Named profile from ~/.aws/config. Leave unset to use the default chain.",
    )

    bedrock_model_id: str = Field(
        default="",
        description="Run 'python -m analyst_agent.agent.models' to list what your account has",
    )
    bedrock_max_tokens: int = 8192
    bedrock_temperature: float | None = None
    bedrock_thinking_budget: int | None = Field(
        default=None,
        description="Enables extended thinking on models that support it. Minimum 1024.",
    )

    agent_max_turns: int = Field(
        default=16,
        description=(
            "Tool-call turns before the run is abandoned. A full pass is roughly "
            "describe_schema, resolve_company, three to five queries, then the answer; "
            "the rest is headroom for correcting a failed query."
        ),
    )

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8765
    mcp_url: str = ""

    api_url: str = "http://127.0.0.1:8000"

    @field_validator(
        "aws_profile", "bedrock_temperature", "bedrock_thinking_budget", mode="before"
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("bedrock_thinking_budget")
    @classmethod
    def _min_budget(cls, value: int | None) -> int | None:
        if value is not None and value < 1024:
            raise ValueError("bedrock_thinking_budget must be at least 1024 when set")
        return value

    @property
    def resolved_mcp_url(self) -> str:
        return self.mcp_url or f"http://{self.mcp_host}:{self.mcp_port}/mcp"

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n, None)]
        if missing:
            raise MissingSetting(missing)


class MissingSetting(RuntimeError):
    def __init__(self, names: list[str]) -> None:
        self.names = names
        listed = ", ".join(n.upper() for n in names)
        super().__init__(f"Missing required setting(s): {listed}. See .env.example.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
