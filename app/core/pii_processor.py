"""
PII detection and reversible tokenization using Microsoft Presidio.

Pipeline:
  raw_text
    → Presidio detect (standard + custom Indian PII)
    → assign stable tokens (PERSON_1, AADHAAR_1 …)
    → return anonymized_text + list[PIIToken]

Only anonymized_text is sent to the LLM.
Original values are Fernet-encrypted and stored in pii_mappings table.
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider


@dataclass
class PIIToken:
    token: str          # e.g. "PERSON_1"
    entity_type: str    # Presidio entity type
    original_value: str # raw PII value


@dataclass
class PIIResult:
    anonymized_text: str
    tokens: list[PIIToken] = field(default_factory=list)
    audit: dict[str, int] = field(default_factory=dict)   # entity_type → count
    processing_time_ms: int = 0


def _build_analyzer() -> AnalyzerEngine:
    """Build Presidio AnalyzerEngine with custom Indian PII recognizers."""
    # Use a small spacy model; en_core_web_sm must be installed
    nlp_config = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}
    provider = NlpEngineProvider(nlp_configuration=nlp_config)
    nlp_engine = provider.create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])

    # Aadhaar number: 12 digits, optionally spaced as 4-4-4
    aadhaar_recognizer = PatternRecognizer(
        supported_entity="AADHAAR_NUMBER",
        patterns=[
            Pattern(
                name="aadhaar",
                regex=r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
                score=0.9,
            )
        ],
        context=["aadhaar", "uid", "unique identification", "आधार"],
    )

    # PAN: 5 uppercase letters + 4 digits + 1 uppercase letter
    pan_recognizer = PatternRecognizer(
        supported_entity="PAN_NUMBER",
        patterns=[
            Pattern(
                name="pan",
                regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
                score=0.95,
            )
        ],
        context=["pan", "permanent account", "income tax"],
    )

    # Indian mobile: starts with 6-9, 10 digits, optional +91/0 prefix
    phone_recognizer = PatternRecognizer(
        supported_entity="IN_PHONE_NUMBER",
        patterns=[
            Pattern(
                name="indian_phone",
                regex=r"(?:\+91|91|0)?[\s\-]?([6-9]\d{2})[\s\-]?\d{3}[\s\-]?\d{4}\b",
                score=0.85,
            )
        ],
        context=["phone", "mobile", "contact", "number", "call"],
    )

    # Bank account: 9-18 digits (rough Indian bank account pattern)
    bank_account_recognizer = PatternRecognizer(
        supported_entity="BANK_ACCOUNT",
        patterns=[
            Pattern(
                name="bank_account",
                regex=r"\b\d{9,18}\b",
                score=0.5,
            )
        ],
        context=["account", "bank", "savings", "current", "ifsc"],
    )

    analyzer.registry.add_recognizer(aadhaar_recognizer)
    analyzer.registry.add_recognizer(pan_recognizer)
    analyzer.registry.add_recognizer(phone_recognizer)
    analyzer.registry.add_recognizer(bank_account_recognizer)

    return analyzer


# Module-level singleton
_analyzer: AnalyzerEngine | None = None


def get_analyzer() -> AnalyzerEngine:
    global _analyzer
    if _analyzer is None:
        _analyzer = _build_analyzer()
    return _analyzer


# Standard entities Presidio already handles
STANDARD_ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "LOCATION", "DATE_TIME",
    "CREDIT_CARD", "IBAN_CODE", "URL",
]
CUSTOM_ENTITIES = ["AADHAAR_NUMBER", "PAN_NUMBER", "IN_PHONE_NUMBER", "BANK_ACCOUNT"]
ALL_ENTITIES = STANDARD_ENTITIES + CUSTOM_ENTITIES


def anonymize(text: str) -> PIIResult:
    """
    Detect all PII in text, replace with stable tokens, return PIIResult.
    Tokens are document-scoped: counters reset per call.
    """
    t0 = time.monotonic()
    analyzer = get_analyzer()

    results = analyzer.analyze(text=text, language="en", entities=ALL_ENTITIES)

    # Sort by start position descending so we can replace without offset shift
    results_sorted = sorted(results, key=lambda r: r.start, reverse=True)

    # Deduplicate overlapping spans (keep highest-score)
    deduplicated = []
    last_start = len(text) + 1
    for r in results_sorted:
        if r.end <= last_start:
            deduplicated.append(r)
            last_start = r.start

    # Build token counter per entity type
    counters: dict[str, int] = defaultdict(int)
    tokens: list[PIIToken] = []
    audit: dict[str, int] = defaultdict(int)

    anonymized = text
    for r in deduplicated:
        original_value = text[r.start:r.end]
        counters[r.entity_type] += 1
        token_label = f"{r.entity_type}_{counters[r.entity_type]}"
        anonymized = anonymized[: r.start] + f"[{token_label}]" + anonymized[r.end :]
        tokens.append(PIIToken(token=token_label, entity_type=r.entity_type, original_value=original_value))
        audit[r.entity_type] += 1

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return PIIResult(
        anonymized_text=anonymized,
        tokens=tokens,
        audit=dict(audit),
        processing_time_ms=elapsed_ms,
    )
