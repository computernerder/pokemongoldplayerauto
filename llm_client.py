import json
from typing import List, Dict, Any, Optional

import requests

# Simple client for a local OpenAI-compatible endpoint (e.g., LM Studio / Ollama)
# Default URL matches your example: http://localhost:1234/v1/chat/completions


def chat(
    messages: List[Dict[str, str]],
    *,
    model: str = "qwen/qwen3-14b",
    temperature: float = 0.7,
    max_tokens: int = -1,
    stream: bool = False,
    url: str = "http://localhost:1234/v1/chat/completions",
    extra: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Call a local OpenAI-compatible chat endpoint.

    Args:
        messages: [{'role': 'system'|'user'|'assistant', 'content': str}, ...]
        model: model name exposed by the server.
        temperature: sampling temperature.
        max_tokens: -1 or server-dependent unlimited.
        stream: whether to request streaming responses (not handled here).
        url: endpoint URL.
        extra: optional extra payload keys.
        timeout: request timeout seconds.

    Returns:
        Parsed JSON response as dict.
    """

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if extra:
        payload.update(extra)

    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    example_messages = [
        {"role": "system", "content": "Always answer in rhymes. Today is Thursday"},
        {"role": "user", "content": "What day is it today?"},
    ]
    reply = chat(example_messages)
    print(json.dumps(reply, indent=2))
