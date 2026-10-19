from collections.abc import Iterable
import re

from pydantic import BaseModel

BRACKET_TIMESTAMP_PATTERN = re.compile(
    r"^\s*[\[\(]\d{4}-\d{2}-\d{2}[ T][\d:.,]+\s*[\]\)]\s*"
)
BARE_TIMESTAMP_PATTERN = re.compile(r"^\s*\d{4}-\d{2}-\d{2}[ T][\d:.,]+\s*")
LABELED_FIELD_PATTERN = re.compile(
    r"\b(?:host|container_id|container|node|executor|application_id|attempt_id)=\S+"
)
UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
HEX_PATTERN = re.compile(r"\b0x[0-9a-fA-F]+\b")
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\b")
WHITESPACE_PATTERN = re.compile(r"\s+")
EXCEPTION_PATTERN = re.compile(
    r"((?:[A-Za-z_$][\w$]*\.)+[A-Za-z_$][\w$]*(?:Exception|Error|Failure|Throwable))"
    r"(?::\s*(.*))?$"
)
SHORT_EXCEPTION_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z0-9]*(?:Exception|Error))\b(?::\s*(.*))?$"
)
SEVERITY_PATTERN = re.compile(r"\b(?:ERROR|FATAL|CRITICAL)\b")

RESOURCE_MARKERS = (
    "out of memory",
    "outofmemoryerror",
    "heap space",
    "gc overhead",
    "container killed",
    "killed by yarn",
    "exceeding memory limits",
    "no space left on device",
    "backpressure",
)

MESSAGE_MAX_CHARS = 120


class SignatureHit(BaseModel):
    signature: str
    count: int
    sample: str


def normalize_log_line(line: str) -> str:
    normalized = BRACKET_TIMESTAMP_PATTERN.sub("", line.strip())
    normalized = BARE_TIMESTAMP_PATTERN.sub("", normalized)
    normalized = LABELED_FIELD_PATTERN.sub("", normalized)
    normalized = UUID_PATTERN.sub("<id>", normalized)
    normalized = HEX_PATTERN.sub("<hex>", normalized)
    normalized = NUMBER_PATTERN.sub("<n>", normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def _truncate_message(message: str) -> str:
    message = message.strip()
    if len(message) <= MESSAGE_MAX_CHARS:
        return message
    return message[: MESSAGE_MAX_CHARS - 3].rstrip() + "..."


def extract_signature(line: str) -> str | None:
    if not line or not line.strip():
        return None

    normalized = normalize_log_line(line)
    if not normalized:
        return None

    match = EXCEPTION_PATTERN.search(normalized) or SHORT_EXCEPTION_PATTERN.search(normalized)
    if match:
        exception_name = match.group(1)
        message = _truncate_message(match.group(2) or "")
        return f"{exception_name}: {message}" if message else exception_name

    lowered = normalized.lower()
    if SEVERITY_PATTERN.search(normalized) and any(
        marker in lowered for marker in RESOURCE_MARKERS
    ):
        return _truncate_message(normalized)

    return None


def extract_signatures(lines: Iterable[str], limit: int = 5) -> list[SignatureHit]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    counts: dict[str, int] = {}
    samples: dict[str, str] = {}

    for line in lines:
        signature = extract_signature(line)
        if signature is None:
            continue
        counts[signature] = counts.get(signature, 0) + 1
        samples.setdefault(signature, line.strip())

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        SignatureHit(signature=signature, count=count, sample=samples[signature])
        for signature, count in ordered[:limit]
    ]
