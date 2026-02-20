from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

FIGMA_API_BASE = os.getenv("FIGMA_API_BASE", "https://api.figma.com/v1")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
FIGMA_API_TOKEN = os.getenv("FIGMA_API_TOKEN", "")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "hf")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "HuggingFaceTB/SmolLM3-3B")
LLM_MODEL_SUFFIX = os.getenv("LLM_MODEL_SUFFIX", "hf-inference")
DEFAULT_HF_BASE = f"https://router.huggingface.co/hf-inference/models/{LLM_MODEL_NAME}"
DEFAULT_HF_ROUTER_BASE = "https://router.huggingface.co"
LLM_API_BASE = os.getenv(
    "LLM_API_BASE",
    DEFAULT_HF_BASE
    if LLM_PROVIDER == "hf"
    else DEFAULT_HF_ROUTER_BASE
    if LLM_PROVIDER == "hf_router"
    else "http://localhost:8001",
)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
LLM_MAX_NEW_TOKENS = int(os.getenv("LLM_MAX_NEW_TOKENS", "512"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN", "")
