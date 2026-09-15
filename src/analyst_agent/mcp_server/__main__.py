import os

from analyst_agent.mcp_server import server
from analyst_agent.mcp_server.repository import Repository, build_engine


def main() -> None:
    server.configure(Repository(build_engine()))
    server.mcp.run(
        transport="streamable-http",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8765")),
    )


if __name__ == "__main__":
    main()
