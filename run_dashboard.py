#!/usr/bin/env python3
"""Start the Peptide Ecommerce Automation Dashboard."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from dashboard.app import create_app
import config

if __name__ == "__main__":
    app = create_app()
    print(f"\n{'='*55}")
    print(f"  {config.agent.brand_name} — Automation Dashboard")
    print(f"  http://{config.dashboard.host}:{config.dashboard.port}")
    print(f"{'='*55}\n")
    app.run(
        host=config.dashboard.host,
        port=config.dashboard.port,
        debug=config.dashboard.debug,
    )
