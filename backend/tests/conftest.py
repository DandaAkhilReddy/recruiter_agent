from __future__ import annotations

import os

# Ensure tests run with safe defaults regardless of host env
os.environ.setdefault("ENV", "local")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/recruiter")
os.environ.setdefault("AOAI_API_KEY", "test")
os.environ.setdefault("AOAI_ENDPOINT", "https://test.openai.azure.com/")
