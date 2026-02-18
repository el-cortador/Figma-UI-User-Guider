from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

FIGMA_API_BASE = os.getenv("FIGMA_API_BASE", "https://api.figma.com/v1")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
