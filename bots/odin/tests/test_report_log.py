from pathlib import Path

from odin.services.report_log import ModerationRecord, ReportLog


def test_append_and_query_newest_first(tmp_path: Path):
    log = ReportLog(tmp_path)
    log.append(ModerationRecord("warn", "100", "mod", target_id="u1", reason="first"))
    log.append(ModerationRecord("timeout", "100", "mod", target_id="u1", reason="second"))
    log.append(ModerationRecord("warn", "100", "mod", target_id="u2", reason="other user"))
    log.append(ModerationRecord("warn", "200", "mod", target_id="u1", reason="other guild"))

    records = log.for_target("100", "u1")
    assert [r.reason for r in records] == ["second", "first"]
    assert log.for_target("100", "u1", limit=1)[0].reason == "second"
    assert log.for_target("100", "nobody") == []
    assert log.for_target("999", "u1") == []
    assert (tmp_path / "moderation-100.jsonl").is_file()
    assert (tmp_path / "moderation-200.jsonl").is_file()
    # Non-digit guild ids never produce path traversal; they collapse to "unknown".
    assert log.path_for("../evil").name == "moderation-unknown.jsonl"


def test_corrupt_lines_are_skipped(tmp_path: Path):
    log = ReportLog(tmp_path)
    path = log.append(ModerationRecord("warn", "123", "mod", target_id="u1", reason="ok"))
    path.write_text(path.read_text() + 'not json\n{"action":"warn"}\n')
    assert [r.reason for r in log.for_target("123", "u1")] == ["ok"]


def test_roundtrip_ignores_unknown_keys():
    line = ModerationRecord("purge", "1", "m", extra={"deleted": 3}).to_json()
    line = line[:-1] + ',"future_field":1}'
    record = ModerationRecord.from_json(line)
    assert record.action == "purge" and record.extra == {"deleted": 3}
