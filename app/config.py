from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

FIGMA_API_BASE = os.getenv("FIGMA_API_BASE", "https://api.figma.com/v1")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))

LLM_API_BASE = os.getenv("LLM_API_BASE", "http://localhost:8001")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "dim014/deepseek-r1-finetuned")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))
