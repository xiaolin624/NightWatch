from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel, Field

from nightwatch.ingest.signatures import SignatureHit, extract_signatures
from nightwatch.models.incident import LogSnippet
from nightwatch.retrieval.slicer import extract_relevant_log_slices

SIGNATURE_HEADER = "错误签名（按出现次数）"
SLICE_HEADER = "日志切片（按相关性，已按时间窗收敛）"
RAW_SOURCE = "raw"


class LogDigest(BaseModel):
    slices: list[LogSnippet] = Field(default_factory=list)
    signatures: list[SignatureHit] = Field(default_factory=list)
    total_lines: int = 0
    kept_lines: int = 0
    before_chars: int = 0
    after_chars: int = 0

    @property
    def compression_ratio(self) -> float:
        if self.before_chars <= 0:
            return 0.0
        return round(1 - (self.after_chars / self.before_chars), 4)


def _joined_passthrough(lines: list[str]) -> list[LogSnippet]:
    if not lines:
        return []
    return [
        LogSnippet(
            source=RAW_SOURCE,
            host="",
            offset_start=0,
            offset_end=len(lines) - 1,
            content="\n".join(lines),
            score=0.0,
        )
    ]


def build_digest(
    raw_lines: Iterable[str],
    failure_timestamp: datetime | None = None,
    seconds_before: int = 120,
    seconds_after: int = 120,
    max_snippets: int = 20,
    signature_limit: int = 5,
) -> LogDigest:
    lines = [line for line in raw_lines if line is not None]
    before_chars = sum(len(line) for line in lines)

    if failure_timestamp is None:
        slices = _joined_passthrough(lines)
    else:
        slices = extract_relevant_log_slices(
            lines,
            failure_timestamp=failure_timestamp,
            seconds_before=seconds_before,
            seconds_after=seconds_after,
            max_snippets=max_snippets,
        )
        if not slices:
            slices = _joined_passthrough(lines)

    kept_lines: list[str] = []
    for snippet in slices:
        kept_lines.extend(line for line in snippet.content.splitlines() if line.strip())

    signatures = extract_signatures(kept_lines or lines, limit=signature_limit)

    return LogDigest(
        slices=slices,
        signatures=signatures,
        total_lines=len(lines),
        kept_lines=len(kept_lines),
        before_chars=before_chars,
    )


def _render_signatures(signatures: list[SignatureHit]) -> str:
    if not signatures:
        return ""
    rows = [SIGNATURE_HEADER]
    for index, hit in enumerate(signatures, start=1):
        rows.append(f"{index}. {hit.signature}  × {hit.count}")
        rows.append(f"   示例: {hit.sample}")
    return "\n".join(rows)


def _render_slices(slices: list[LogSnippet]) -> str:
    if not slices:
        return ""
    rows = [SLICE_HEADER]
    for index, snippet in enumerate(slices, start=1):
        rows.append(
            f"[Snippet {index}] source={snippet.source} host={snippet.host} "
            f"offset={snippet.offset_start}-{snippet.offset_end} score={snippet.score}"
        )
        rows.append(snippet.content.strip())
    return "\n".join(rows)


def render_digest(digest: LogDigest, max_chars: int) -> str:
    if max_chars <= 0:
        return ""

    signature_block = _render_signatures(digest.signatures)
    slice_block = _render_slices(digest.slices)

    if not signature_block and not slice_block:
        digest.after_chars = 0
        return ""

    if not slice_block:
        rendered = signature_block
    elif not signature_block:
        rendered = slice_block
    else:
        rendered = f"{signature_block}\n\n{slice_block}"

    if len(rendered) > max_chars:
        rendered = rendered[:max_chars]

    digest.after_chars = len(rendered)
    return rendered
