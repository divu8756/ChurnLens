"""On-demand retention message for one customer's next best offer (runbook T5b.4).

The LLM (fast tier) sees only the offer name and the customer's top 3 reasons. Every
number it writes must come from the offer name (app/validation.py rules); one retry with
feedback, then a fixed template. Results are cached per customer in the session folder,
so the same customer never costs a second LLM call.
"""

import json
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app import llm
from app.prompts.loader import render_prompt
from app.validation import check_text, numbers_in

PROMPT = ("offer_message", 1)
TIMEOUT_S = 30
MAX_ATTEMPTS = 2
SMS_LIMIT = 160
CACHE_FILE = "offer_messages.json"
_cache_lock = threading.Lock()


class OfferMessage(BaseModel):
    message: str = Field(min_length=1, max_length=600)
    sms: str = Field(min_length=1, max_length=SMS_LIMIT)


def allowed_figures(offer: str) -> list[dict[str, Any]]:
    """The only numbers a message may contain: the ones written in the offer name."""
    return [{"value": n, "display": ""} for n, _ in numbers_in(offer)]


def validate_offer_message(message: dict[str, str], offer: str) -> list[str]:
    figures = allowed_figures(offer)
    problems = [f"message: {p}" for p in check_text(message.get("message", ""), figures)]
    problems += [f"sms: {p}" for p in check_text(message.get("sms", ""), figures)]
    if len(message.get("sms", "")) > SMS_LIMIT:
        problems.append(f"sms is {len(message['sms'])} characters (limit {SMS_LIMIT})")
    text = f"{message.get('message', '')} {message.get('sms', '')}".casefold()
    if offer.casefold() not in text:
        problems.append(f"the offer name {offer!r} must appear unchanged")
    return problems


def template_message(offer: str) -> dict[str, str]:
    sms = f"Thank you for being with us. We'd like to offer you: {offer}. Reply YES to claim it."
    if len(sms) > SMS_LIMIT:
        sms = f"Offer for you: {offer}"[:SMS_LIMIT]
    return {"message": f"Thank you for being a valued customer. We would like to offer you "
                       f"{offer}; reply or visit your account to claim it.",
            "sms": sms}


def generate(offer: str, reasons: list[str]) -> dict[str, Any]:
    facts = json.dumps({"offer": offer, "reasons": reasons[:3]}, ensure_ascii=False)
    feedback = ""
    problems: list[str] = []
    for _ in range(2):  # first try, then one retry with the problems as feedback
        prompt = render_prompt(*PROMPT, facts_json=facts, feedback=feedback)
        try:
            result = llm.structured_call("fast", 0.4, prompt, OfferMessage,
                                         timeout_s=TIMEOUT_S, max_attempts=MAX_ATTEMPTS)
        except llm.LLMUnavailable as exc:
            return {**template_message(offer), "source": "template",
                    "problems": [f"AI unavailable: {exc}"]}
        message = result.model_dump()
        problems = validate_offer_message(message, offer)
        if not problems:
            return {**message, "source": "ai", "problems": []}
        feedback = "Fix these issues from your last answer:\n- " + "\n- ".join(problems)
    return {**template_message(offer), "source": "template", "problems": problems}


def cached_message(session_dir: Path, customer_id: str, offer: str,
                   reasons: list[str]) -> tuple[dict[str, Any], bool]:
    """(message, came_from_cache). The cache is keyed by customer and offer."""
    path = session_dir / CACHE_FILE
    key = f"{customer_id}␟{offer}"
    with _cache_lock:
        cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if key in cache:
            return cache[key], True
    result = generate(offer, reasons)
    with _cache_lock:
        cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        cache.setdefault(key, result)
        path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        return cache[key], False
