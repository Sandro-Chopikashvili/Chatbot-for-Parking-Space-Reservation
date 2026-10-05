# Guardrails for the CityPark assistant:
# - Block unsafe requests, prompt injection, and attempts to access private data.
# - Detect and redact sensitive information such as names, phone numbers, emails, and car plates.
# - Allow legitimate CityPark terms and the user's own booking information.
# - check_input() handles input safety, while redact() handles output privacy.

import re
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

# Types of sensitive information that should be detected and protected.
ENTITIES = ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", "IBAN_CODE", "CAR_PLATE"]
# CityPark and location terms that the NER model should not treat as people's names.
FACILITY_TERMS = ["CityPark", "Rustaveli", "Kostava", "Tbilisi", "Freedom Square", "Opera House"]
# Message returned when a user's request is blocked.
BLOCK_MSG = ("I can't help with that request. I can answer questions about CityPark "
             "and help you reserve a space.")

# Patterns used to detect prompt injection and requests for unauthorized information.
BLOCK_PATTERNS = [re.compile(p, re.I) for p in [
    r"ignore\s+(all\s+|any\s+|your\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"(disregard|forget)\s+(all\s+|your\s+|the\s+)?(previous|prior|above|earlier|safety)?\s*(instructions?|rules?|guidelines?)",
    r"(reveal|show|print|repeat|display|tell me)\b.{0,30}\b(system prompt|your instructions|hidden instructions)",
    r"\b(other|another|all|every|previous)\s+(customers?|clients?|users?|drivers?)('s|')?\s*(data|info|information|details|phones?|emails?|plates?|reservations?|bookings?|names?)",
    r"\b(phone number|email|e-mail|car number|plate)s?\s+(of|for)\s+(customer|client|mr\.?|mrs\.?|ms\.?|another|someone|somebody|other)\b",
    r"\b(admin|administrator)\s+(override|code|password|credentials?)",
    r"\b(vip list|internal notes?|private[_\s]notes?|confidential)\b",
    r"\b(developer mode|jailbreak|dan mode|do anything now)\b",
    r"(pretend|act as|you are now)\b.{0,40}\b(admin|administrator|developer|root|unrestricted)",
    r"\b(dump|list|export)\b.{0,30}\b(database|reservations|customers|all data)\b",
]]


# Create and cache the Presidio engines used for detecting and anonymizing PII.
@lru_cache(maxsize=1)
def _engines():
    analyzer = AnalyzerEngine()
    analyzer.registry.add_recognizer(PatternRecognizer(
        supported_entity="CAR_PLATE",
        patterns=[Pattern("plate", r"\b[A-Z]{2}-\d{3}-[A-Z]{2}\b", 0.8)],
    ))
    return analyzer, AnonymizerEngine()

# Check whether the user's input contains a blocked request.
def check_input(text: str) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means the message must be blocked."""
    for pat in BLOCK_PATTERNS:
        if pat.search(text):
            return False, pat.pattern
    return True, ""

# Detect and redact sensitive information while allowing approved values to remain.
def redact(text: str, allow: list[str] | None = None) -> str:
    """Replace PII with <ENTITY> tags. `allow` = values that may stay (the user's own booking data)."""
    analyzer, anonymizer = _engines()
    allow_list = FACILITY_TERMS + [a for a in (allow or []) if a]
    results = analyzer.analyze(text=text, entities=ENTITIES, language="en", allow_list=allow_list)
    result = anonymizer.anonymize(text=text, analyzer_results=results)
    return getattr(result, "text", None) or getattr(result, "anonymized_text", text)