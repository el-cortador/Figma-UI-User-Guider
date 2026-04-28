from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Use an explicit path so .env is found regardless of working directory.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Figma API
# ---------------------------------------------------------------------------

FIGMA_API_BASE = os.getenv("FIGMA_API_BASE", "https://api.figma.com/v1")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))
FIGMA_API_TOKEN = os.getenv("FIGMA_API_TOKEN", "")

# ---------------------------------------------------------------------------
# LLM (OpenRouter — OpenAI-compatible)
# ---------------------------------------------------------------------------

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://openrouter.ai/api/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "z-ai/glm-4.7-flash")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

# Optional headers recommended by OpenRouter for request attribution.
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Figma UI User Guider")