from datetime import datetime

from nightwatch.retrieval.digest import build_digest, render_digest


LOG_LINES = [
    "2026-09-01 12:00:00 INFO starting executor",
    "2026-09-01 12:00:30 INFO task assigned",
    "2026-09-01 12:00:58 ERROR java.lang.OutOfMemoryError: Java heap space",
    "2026-09-01 12:00:59 ERROR java.lang.OutOfMemoryError: Java heap space",
    "2026-09-01 12:01:00 ERROR Container killed by YARN for exceeding memory limits",
    "2026-09-01 12:01:01 ERROR org.apache.spark.SparkException: Job aborted due to stage failure",
    "2026-09-01 14:00:00 INFO unrelated afternoon log",
]


def test_build_digest_without_timestamp_keeps_all_lines():
    digest = build_digest(LOG_LINES)

    assert digest.total_lines == len(LOG_LINES)
    assert digest.kept_lines == len(LOG_LINES)
    assert digest.signatures


def test_build_digest_windows_around_failure():
    digest = build_digest(
        LOG_LINES,
        failure_timestamp=datetime(2026, 9, 1, 12, 1, 0),
        seconds_before=120,
        seconds_after=120,
    )

    joined = "\n".join(snippet.content for snippet in digest.slices)
    assert "OutOfMemoryError" in joined
    # 下午那条无关日志必须被时间窗挡掉
    assert "unrelated afternoon log" not in joined
    assert digest.kept_lines < digest.total_lines


def test_build_digest_extracts_signatures():
    digest = build_digest(LOG_LINES)

    signatures = [hit.signature for hit in digest.signatures]
    assert any("OutOfMemoryError" in signature for signature in signatures)


def test_render_digest_puts_signatures_first():
    digest = build_digest(LOG_LINES)
    rendered = render_digest(digest, max_chars=4000)

    signature_index = rendered.find("错误签名")
    slice_index = rendered.find("日志切片")

    assert signature_index != -1
    assert slice_index != -1
    assert signature_index < slice_index


def test_render_digest_respects_max_chars():
    digest = build_digest(LOG_LINES)
    rendered = render_digest(digest, max_chars=200)

    assert len(rendered) <= 200


def test_digest_reports_char_reduction():
    digest = build_digest(LOG_LINES)
    rendered = render_digest(digest, max_chars=4000)

    assert digest.before_chars > 0
    assert digest.after_chars == len(rendered)


def test_build_digest_empty_input():
    digest = build_digest([])

    assert digest.total_lines == 0
    assert digest.slices == []
    assert digest.signatures == []
    assert render_digest(digest, max_chars=1000) == ""
