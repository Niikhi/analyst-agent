from analyst_agent.config import get_settings
from analyst_agent.mcp_server import server
from analyst_agent.mcp_server.repository import Repository, build_engine


def main() -> None:
    settings = get_settings()
    server.configure(Repository(build_engine()))
    server.mcp.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )


if __name__ == "__main__":
    main()
