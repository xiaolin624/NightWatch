from nightwatch.ingest.signatures import (
    extract_signature,
    extract_signatures,
    normalize_log_line,
)


def test_normalize_log_line_strips_timestamp_and_host():
    line = "[2026-09-01 12:00:00,123] ERROR host=worker-01 java.lang.OutOfMemoryError: Java heap space"
    normalized = normalize_log_line(line)

    assert "2026-09-01" not in normalized
    assert "worker-01" not in normalized
    assert "OutOfMemoryError" in normalized


def test_normalize_log_line_collapses_numbers():
    a = normalize_log_line("2026-09-01 12:00:00 ERROR Task 12 in stage 3 failed 4 times")
    b = normalize_log_line("2026-09-01 12:00:01 ERROR Task 77 in stage 9 failed 8 times")

    assert a == b


def test_extract_signature_spark_exception():
    line = (
        "2026-09-01 12:00:05 ERROR org.apache.spark.SparkException: "
        "Job aborted due to stage failure: Task 0 in stage 1.0 failed 4 times"
    )
    signature = extract_signature(line)

    assert signature is not None
    assert "org.apache.spark.SparkException" in signature
    assert "<n>" in signature


def test_extract_signature_caused_by():
    line = "\tCaused by: java.io.IOException: No space left on device"
    signature = extract_signature(line)

    assert signature is not None
    assert "java.io.IOException" in signature


def test_extract_signature_flink_exception():
    line = (
        "[2026-09-01 12:00:00] org.apache.flink.runtime.jobmanager.scheduler."
        "NoResourceAvailableException: Could not acquire the minimum required resources."
    )
    signature = extract_signature(line)

    assert signature is not None
    assert "NoResourceAvailableException" in signature


def test_extract_signature_returns_none_for_plain_line():
    assert extract_signature("2026-09-01 12:00:00 INFO starting executor") is None
    assert extract_signature("") is None


def test_extract_signatures_aggregates_counts():
    lines = [
        "2026-09-01 12:00:00 ERROR java.lang.OutOfMemoryError: Java heap space",
        "2026-09-01 12:00:01 ERROR java.lang.OutOfMemoryError: Java heap space",
        "2026-09-01 12:00:02 ERROR java.lang.OutOfMemoryError: Java heap space",
        "2026-09-01 12:00:03 ERROR org.apache.spark.SparkException: Job aborted",
        "2026-09-01 12:00:04 INFO starting executor",
    ]
    hits = extract_signatures(lines)

    assert len(hits) == 2
    assert hits[0].count == 3
    assert "OutOfMemoryError" in hits[0].signature
    assert hits[0].sample.startswith("2026-09-01")


def test_extract_signatures_sorts_by_count_desc():
    lines = [
        "ERROR org.apache.spark.SparkException: a",
        "ERROR java.lang.OutOfMemoryError: b",
        "ERROR java.lang.OutOfMemoryError: b",
    ]
    hits = extract_signatures(lines)

    assert hits[0].count == 2
    assert "OutOfMemoryError" in hits[0].signature


def test_extract_signatures_respects_limit():
    lines = [
        "ERROR java.lang.OutOfMemoryError: a",
        "ERROR java.io.IOException: b",
        "ERROR org.apache.spark.SparkException: c",
        "ERROR java.lang.IllegalStateException: d",
    ]
    hits = extract_signatures(lines, limit=2)

    assert len(hits) == 2


def test_extract_signatures_empty_input():
    assert extract_signatures([]) == []
