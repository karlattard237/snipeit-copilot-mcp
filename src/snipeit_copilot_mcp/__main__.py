"""Command-line entry point."""

from __future__ import annotations

import sys

from .config import ConfigError, load_settings
from .logging import configure_logging


def main() -> None:
    try:
        settings = load_settings(require_credentials=True)
        configure_logging(settings.log_level)
        from .server import build_server

        mcp = build_server(settings)
    except ConfigError as exc:
        configure_logging("INFO")
        print(f"Configuration error: {exc.message}", file=sys.stderr)
        raise SystemExit(2) from exc
    if settings.mcp_transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()

