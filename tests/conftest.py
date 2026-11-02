"""Shared test setup: faculty.py reads CHAVER_BACKEND at import; keep tests off the network."""
import os

os.environ.setdefault("CHAVER_BACKEND", "anthropic")
