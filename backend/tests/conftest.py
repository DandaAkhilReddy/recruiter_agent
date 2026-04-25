from __future__ import annotations

import os

# Ensure tests run with safe defaults regardless of host env.
# IMPORTANT: this file is loaded BEFORE any test module imports `app`, so any
# env var set here is in place when `get_settings()` first runs.

# When the integration suite is targeting a separate test DB (via
# TEST_DATABASE_URL), promote it to DATABASE_URL so the orchestrator's
# module-level SessionLocal binds to the test DB instead of the production
# default. The orchestrator opens its own sessions for the background
# outreach task and bypasses FastAPI's get_db override, so this env-level
# redirect is the cleanest way to keep the test isolated.
if _test_url := os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = _test_url

os.environ.setdefault("ENV", "local")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/recruiter")
os.environ.setdefault("AOAI_API_KEY", "test")
os.environ.setdefault("AOAI_ENDPOINT", "https://test.openai.azure.com/")
