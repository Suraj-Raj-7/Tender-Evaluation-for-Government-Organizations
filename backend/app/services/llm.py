"""
backend/app/services/llm.py
--------------------------------
Purpose: The single place in the whole codebase that talks to an AI
language model. Every other file that needs "read this text, give me
an answer" (tender_parser.py, bidder_parser.py -- built next) calls
call_llm() here and never imports Gemini/Groq/OpenRouter directly.

Why this file exists: The project spec requires a fallback chain --
Gemini first (free, generous daily limit), Groq if Gemini fails or is
rate-limited, OpenRouter as a last resort. Centralizing this here means
that chain is written exactly once, and swapping/adding a provider
later means editing one file, not hunting through the whole codebase.

IMPORTANT: This file only gets a raw text answer back from the model.
It does NOT parse that answer into structured data (e.g. JSON) -- that
responsibility belongs to whichever file calls this one, since only
the caller knows what shape of answer it actually asked for. The
json_mode flag below only tells the PROVIDER to guarantee valid JSON
syntax -- it does not tell this file what that JSON should contain.
"""

import google.generativeai as genai
from groq import Groq
import requests

from app.config import settings


class LLMProviderError(Exception):
    """
    Purpose: A single, consistent exception type raised when one
    specific provider (Gemini, Groq, or OpenRouter) fails to answer.

    Where it's used: Raised inside each _call_*() function below.
    Caught by call_llm(), which uses it to decide "this provider
    failed, try the next one" instead of crashing the whole request.
    """
    def __init__(self, provider: str, original_error: Exception):
        self.provider = provider
        self.original_error = original_error
        super().__init__(f"{provider} failed: {original_error}")


def _call_gemini(prompt: str, json_mode: bool) -> str:
    """
    Purpose: Sends a prompt to Gemini 2.5 Flash and returns its text
    response. This is the first (primary) provider tried.

    Where it gets its data: prompt and json_mode are passed in by
    call_llm() below, which got them from whichever caller (e.g.
    tender_parser.py) built the actual extraction instructions.

    Where it's used: Called first, every time, by call_llm().

    Note on json_mode: When True, sets response_mime_type to
    "application/json" -- this tells Gemini's API itself to only ever
    emit syntactically valid JSON, instead of relying on the prompt's
    wording alone (which models sometimes ignore or get slightly wrong).
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        generation_config = (
            genai.GenerationConfig(response_mime_type="application/json")
            if json_mode else None
        )
        model = genai.GenerativeModel(
            "gemini-2.5-flash", generation_config=generation_config
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise LLMProviderError("Gemini", e)


def _call_groq(prompt: str, json_mode: bool) -> str:
    """
    Purpose: Sends a prompt to Groq's hosted Llama 3.3 70B model.
    Tried second, only if Gemini raised an LLMProviderError.

    Where it gets its data: Same prompt string Gemini was given --
    every provider is asked exactly the same question, so switching
    providers never changes what's being asked, only who answers.

    Where it's used: Called by call_llm() only after _call_gemini()
    fails.

    Note on json_mode: Groq's response_format={"type": "json_object"}
    forces syntactically valid JSON. IMPORTANT: Groq's JSON mode
    requires the result to be a JSON *object* (with keys), not a bare
    array -- this is why tender_parser.py asks for {"criteria": [...]}
    rather than a raw [...] array.
    """
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if json_mode else None,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise LLMProviderError("Groq", e)


def _call_openrouter(prompt: str, json_mode: bool) -> str:
    """
    Purpose: Sends a prompt to OpenRouter, a service that itself routes
    to multiple free models. This is the final fallback -- only
    reached if both Gemini and Groq have already failed.

    Where it gets its data: Same prompt string as the other two
    providers. Unlike Gemini/Groq, OpenRouter has no official Python
    library, so this makes a plain HTTP POST request directly.

    Where it's used: Called by call_llm() only as the last resort.
    """
    try:
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
    except Exception as e:
        raise LLMProviderError("OpenRouter", e)


def call_llm(prompt: str, json_mode: bool = False) -> str:
    """
    Purpose: The single public entry point for getting an AI answer
    anywhere in this codebase. Tries Gemini, then Groq, then
    OpenRouter, in that order -- returns the first successful answer.

    Where it gets its data: prompt is built entirely by the caller.
    json_mode is set to True by callers that need guaranteed-valid
    JSON syntax back (e.g. tender_parser.py) -- False (default) for
    plain conversational text.

    Where it's used: Will be called by services/tender_parser.py and
    services/bidder_parser.py, from inside a Celery task in
    workers/tasks.py.

    Raises: RuntimeError, only if ALL three providers fail. The error
    message includes every individual provider's failure reason, so a
    real outage is fully traceable in the Celery worker's logs --
    never a silent, unexplained failure.
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
            return provider_fn(prompt, json_mode)
        except LLMProviderError as e:
            print(f"[llm.py] {e}")
            errors.append(str(e))

    raise RuntimeError(
        "All AI providers failed or are unconfigured:\n" + "\n".join(errors)
    )