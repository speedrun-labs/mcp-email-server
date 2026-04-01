from __future__ import annotations

import argparse
import logging


def cli() -> None:
    parser = argparse.ArgumentParser(description="MCP Mail Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--host", default=None, help="HTTP host (overrides APP_HOST)")
    parser.add_argument("--port", type=int, default=None, help="HTTP port (overrides APP_PORT)")
    parser.add_argument("--log-level", default="info", help="Log level")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.transport == "stdio":
        _run_stdio()
    else:
        _run_http(args.host, args.port)


def _run_stdio() -> None:
    """Run MCP server in stdio mode."""
    from mcp_mail.accounts import AccountRegistry
    from mcp_mail.config import Settings
    from mcp_mail.server import create_mcp_server

    settings = Settings()
    registry = AccountRegistry(settings)
    mcp = create_mcp_server(settings, registry)
    mcp.run()


def _run_http(host: str | None, port: int | None) -> None:
    """Run combined HTTP server (MCP + REST)."""
    import uvicorn

    from mcp_mail.app import create_app
    from mcp_mail.config import Settings

    settings = Settings()
    app = create_app(settings)

    uvicorn.run(
        app,
        host=host or settings.app.host,
        port=port or settings.app.port,
    )


if __name__ == "__main__":
    cli()
