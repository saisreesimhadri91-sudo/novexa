"""
NIVORA WATER MANAGEMENT SYSTEM — PRODUCTION RUNNER
Version: 2.0-STABLE
Author: Senior Full-Stack, Database, QA & Security Engineering Team

Usage:
    python start_production.py
    set PORT=8080 && python start_production.py
"""

import os
import sys

# Ensure workspace root is in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from server import start_server

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    start_server(port=port, host=host)
