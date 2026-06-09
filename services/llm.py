import logging
import threading

from google import genai
from google.genai import types as genai_types
from google.genai import errors as genai_errors

from config import (
    GEMINI_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_OUTPUT_TOKENS,
)


logger = logging.getLogger(__name__)


class LLMConfigError(Exception):
    """Missing or invalid LLM configuration (API key, model name)."""


class LLMRateLimitError(Exception):
    """LLM provider rate limit hit."""


class LLMServerError(Exception):
    """LLM provider network or 5xx error."""


_client: genai.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> genai.Client:
    """Lazy-init Gemini client. Error only when called, not at import."""
    global _client
    with _client_lock:
        if _client is None:
            if not GEMINI_API_KEY:
                raise LLMConfigError(
                    "GEMINI_API_KEY not set. Get a free key at "
                    "https://aistudio.google.com/app/apikey and add to .env."
                )
            _client = genai.Client(api_key=GEMINI_API_KEY)
        return _client


_SAFETY_SETTINGS_OFF = [
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
    ),
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
    ),
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
    ),
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
    ),
]


def generate(
    prompt: str,
    system: str | None = None,
    temperature: float | None = None,
    response_schema: dict | None = None,
    model_name: str | None = None,
) -> str:
    """Provider-agnostic LLM call. Returns raw text (JSON string if response_schema given)."""

    client = _get_client()
    model = model_name or LLM_MODEL
    temp = temperature if temperature is not None else LLM_TEMPERATURE

    config_kwargs: dict = {
        "temperature": temp,
        "max_output_tokens": LLM_MAX_OUTPUT_TOKENS,
        "safety_settings": _SAFETY_SETTINGS_OFF,
    }
    if system is not None:
        config_kwargs["system_instruction"] = system
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema

    config = genai_types.GenerateContentConfig(**config_kwargs)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    except genai_errors.ClientError as e:
        status = getattr(e, "code", None) or getattr(e, "status_code", None)
        if status == 429:
            raise LLMRateLimitError(str(e)) from e
        raise LLMConfigError(str(e)) from e
    except genai_errors.ServerError as e:
        raise LLMServerError(str(e)) from e
    except genai_errors.APIError as e:
        raise LLMServerError(str(e)) from e
    except Exception as e:
        raise LLMServerError(f"Unexpected LLM error: {e}") from e

    text = getattr(response, "text", None)
    if not text:
        raise LLMServerError("LLM returned empty response.")
    return text
