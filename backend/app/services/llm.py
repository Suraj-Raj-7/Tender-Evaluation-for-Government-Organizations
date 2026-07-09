"""
backend/app/services/llm.py
--------------------------------
Purpose: The single place in the whole codebase that talks to an AI
language model. Every other file that needs "read this text, give me
an answer" (tender_parser.py, bidder_parser.py) calls call_llm() here
and never imports Gemini/Groq/OpenRouter directly.

Why this file exists: The project spec requires a fallback chain --
Gemini first (free, generous daily limit), Groq if Gemini fails or is
rate-limited, OpenRouter as a last resort. Each provider is retried a
few times (via tenacity, with exponential backoff) before giving up on
it and moving to the next -- since a transient network hiccup
shouldn't cost an entire provider its turn.
"""

import google.generativeai as genai
from groq import Groq
import requests
from tenacity import retry, wait_exponential, stop_after_attempt

from app.config import settings


class LLMProviderError(Exception):
    """
    Purpose: A single, consistent exception type raised when one
    specific provider (Gemini, Groq, or OpenRouter) fails to answer,
    even after its internal retries were exhausted.

    Where it's used: Raised inside each _call_*() function below.
    Caught by call_llm(), which uses it to decide "this provider
    failed, try the next one" instead of crashing the whole request.
    """
    def __init__(self, provider: str, original_error: Exception):
        self.provider = provider
        self.original_error = original_error
        super().__init__(f"{provider} failed: {original_error}")


# Shared retry policy: 3 attempts total per provider, waiting longer
# between each attempt (2s, then up to 60s) -- gives a transient error
# (network blip, momentary rate limit) a real chance to resolve itself
# before we give up on this provider entirely and move to the next one.
_RETRY_POLICY = dict(
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)


@retry(**_RETRY_POLICY)
def _gemini_request(prompt: str, generation_config) -> str:
    """
    Purpose: The actual Gemini API call, wrapped in tenacity's retry
    policy -- retried up to 3 times with increasing wait before the
    exception is allowed to propagate up to _call_gemini().

    Where it gets its data: prompt and generation_config are passed by
    _call_gemini() below.
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config)
    response = model.generate_content(prompt)
    return response.text


def _call_gemini(prompt: str, json_mode: bool) -> str:
    """
    Purpose: Sends a prompt to Gemini 2.5 Flash and returns its text
    response. This is the first (primary) provider tried.

    Where it's used: Called first, every time, by call_llm().
    """
    try:
        generation_config = (
            genai.GenerationConfig(response_mime_type="application/json")
            if json_mode else None
        )
        return _gemini_request(prompt, generation_config)
    except Exception as e:
        raise LLMProviderError("Gemini", e)


@retry(**_RETRY_POLICY)
def _groq_request(prompt: str, json_mode: bool) -> str:
    """
    Purpose: The actual Groq API call, wrapped in tenacity's retry policy.

    Where it gets its data: prompt and json_mode are passed by
    _call_groq() below.
    """
    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"} if json_mode else None,
    )
    return response.choices[0].message.content


def _call_groq(prompt: str, json_mode: bool) -> str:
    """
    Purpose: Sends a prompt to Groq's hosted Llama 3.3 70B model.
    Tried second, only if Gemini raised an LLMProviderError.

    Where it's used: Called by call_llm() only after _call_gemini()
    fails.
    """
    try:
        return _groq_request(prompt, json_mode)
    except Exception as e:
        raise LLMProviderError("Groq", e)


@retry(**_RETRY_POLICY)
def _openrouter_request(prompt: str, json_mode: bool) -> str:
    """
    Purpose: The actual OpenRouter REST call, wrapped in tenacity's
    retry policy.

    Where it gets its data: prompt and json_mode are passed by
    _call_openrouter() below.
    """
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _call_openrouter(prompt: str, json_mode: bool) -> str:
    """
    Purpose: Sends a prompt to OpenRouter, the final fallback -- only
    reached if both Gemini and Groq have already failed.

    Where it's used: Called by call_llm() only as the last resort.
    """
    try:
        return _openrouter_request(prompt, json_mode)
    except Exception as e:
        raise LLMProviderError("OpenRouter", e)


def call_llm(prompt: str, json_mode: bool = False) -> str:
    """
    Purpose: The single public entry point for getting an AI answer
    anywhere in this codebase. Tries Gemini, then Groq, then
    OpenRouter, in that order -- returns the first successful answer.
    Logs exactly which provider actually answered, for every call --
    required for debugging and for proving the fallback chain works.

    Where it's used: Called by services/tender_parser.py and
    services/bidder_parser.py, from inside a Celery task.

    Raises: RuntimeError, only if ALL three providers fail (after each
    one's internal retries are exhausted).
    """
    errors: list[str] = []

    providers = [
        ("Gemini", settings.GEMINI_API_KEY, _call_gemini),
        ("Groq", settings.GROQ_API_KEY, _call_groq),
        ("OpenRouter", settings.OPENROUTER_API_KEY, _call_openrouter),
    ]

    for name, api_key, provider_fn in providers:
        if not api_key:
            errors.append(f"{name}: skipped (no API key configured)")
            continue

        try:
            result = provider_fn(prompt, json_mode)
            print(f"[llm.py] Used {name} successfully")
            return result
        except LLMProviderError as e:
            print(f"[llm.py] {e}")
            errors.append(str(e))

    raise RuntimeError(
        "All AI providers failed or are unconfigured:\n" + "\n".join(errors)
    )