"""Render-compatible entrypoint for Idea Vending Machine v0.4.

The verified v0.3 server remains available through ``legacy_app``. Public legacy
symbols are re-exported so existing tests and integrations that import ``app``
keep working, while executing ``python app.py`` launches the v0.4 autonomous
entrypoint used in production.
"""

from legacy_app import *  # noqa: F401,F403
from legacy_app import _provider_is_configured, _server_address_from_environ, _utcnow_iso


def main() -> None:
    """Delegate the production process entrypoint to v0.4 without import cycles."""
    from v04_app import main as autonomous_main

    autonomous_main()


if __name__ == "__main__":
    main()
