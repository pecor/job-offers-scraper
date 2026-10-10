"""LLM service: generates personalized application messages via OpenAI-compatible APIs.

Designed to be extended into the multi-model comparison module: each provider is
described by (name, base_url, api_key, model), so adding GPT/Claude/Gemini later
only requires adding providers to the registry.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "Jesteś asystentem pomagającym w procesie rekrutacji. Na podstawie treści ogłoszenia "
    "o pracę oraz CV kandydata napisz spersonalizowaną wiadomość aplikacyjną do rekrutera. "
    "Wiadomość ma być konkretna, oparta na realnych punktach wspólnych między CV a ogłoszeniem, "
    "bez wymyślania faktów. Nie używaj gotowych szablonów ani pustych frazesów. "
    "Zwróć wyłącznie treść wiadomości — bez żadnych komentarzy, nagłówków ani przypisów. "
    "Odpowiadaj po polsku, chyba że ogłoszenie jest w innym języku — wtedy w języku ogłoszenia."
)

# Replacements removing typical AI-writing tells from generated messages.
_AI_TELL_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\u2014"), "-"),          # em-dash
    (re.compile(r"\u2013"), "-"),          # en-dash
    (re.compile(r"\u2212"), "-"),          # minus sign
    (re.compile(r"\u2026"), "..."),        # ellipsis
    (re.compile(r"\u00a0"), " "),          # non-breaking space
    (re.compile(r"\u200b"), ""),           # zero-width space
    (re.compile(r"\u2022"), "-"),          # bullet
    (re.compile(r"\u25cf"), "-"),          # black circle bullet
    # Markdown artifacts that don't belong in plain messages
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
    (re.compile(r"(?m)^#{1,6}\s*"), ""),
    (re.compile(r"(?m)^\s*[-*]\s+"), ""),
    # Collapse triples of spaces/dashes left after replacements
    (re.compile(r"  +"), " "),
]


def sanitize_ai_text(text: str) -> str:
    """Remove characters and formatting typical for AI-generated messages."""
    for pattern, replacement in _AI_TELL_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text.strip()


@dataclass
class LLMResult:
    content: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    @property
    def total_tokens(self) -> Optional[int]:
        if self.prompt_tokens is None and self.completion_tokens is None:
            return None
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)


class LLMService:
    """Wrapper around an OpenAI-compatible chat completions API."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url
        self.model = model
        self._api_key = api_key
        self._client = OpenAI(base_url=base_url, api_key=api_key) if api_key else None

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._client is not None)

    def generate(self, user_prompt: str, system_prompt: str | None = None, temperature: float = 0.7) -> LLMResult:
        """Generate a completion for the given prompt. Output is sanitized (AI tells removed)."""
        if not self.configured:
            raise RuntimeError("LLM API key is not configured (set LLM_API_KEY in .env)")

        response = self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        choice = response.choices[0] if response.choices else None
        raw_content = (choice.message.content or "").strip() if choice and choice.message else ""
        content = sanitize_ai_text(raw_content)
        usage = getattr(response, "usage", None)

        return LLMResult(
            content=content,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        )

    def test_connection(self) -> str:
        """Quick connectivity check; returns short model reply."""
        result = self.generate("Odpowiedz jednym słowem: OK", temperature=0.0)
        return result.content


def build_application_prompt(offer: dict, cv_text: str, instructions: str = "") -> str:
    """Compose the user prompt for a personalized application message."""
    parts = [
        "OGŁOSZENIE O PRACĘ:",
        f"Tytuł: {offer.get('title', '')}",
        f"Firma: {offer.get('company', '')}",
        f"Lokalizacja: {offer.get('location', '')}",
        f"Technologie: {offer.get('technologies', '')}",
        f"Wynagrodzenie: {offer.get('salary_min', '')} - {offer.get('salary_max', '')} "
        f"{offer.get('salary_period', '')}".strip(),
        "",
        "TREŚĆ OGŁOSZENIA:",
        offer.get("description") or "(brak opisu)",
        "",
        "CV KANDYDATA:",
        cv_text.strip(),
    ]
    if instructions:
        parts += ["", "DODATKOWE WYTYCZNE OD KANDYDATA:", instructions.strip()]
    parts += [
        "",
        "Napisz wiadomość aplikacyjną (wstęp do aplikacji / krótki list motywacyjny, "
        "ok. 150-250 słów), która odnosi się bezpośrednio do wymagań z ogłoszenia "
        "i doświadczenia z CV.",
    ]
    return "\n".join(str(p) for p in parts)


def get_default_service() -> LLMService:
    """Default provider from settings (single model for now)."""
    return LLMService(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
    )
