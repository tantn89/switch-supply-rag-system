"""Server-Sent Events formatter for FastAPI StreamingResponse."""
from __future__ import annotations

import json
from typing import Any


def sse(event: str, data: Any) -> str:
    """Format an SSE message block.

    SSE protocol: 'event: <name>\\n' then 'data: <json>\\n\\n'.
    """
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"
