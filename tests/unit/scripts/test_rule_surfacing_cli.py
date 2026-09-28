from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.audits.rule_surfacing import cli


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/audits/build_rule_surfacing_inventory.py"


def _load_audit():
    spec = importlib.util.spec_from_file_location("rule_surfacing_cli_fixture", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def payload():
    return _load_audit().build_audit()


@pytest.fixture
def audit(payload, monkeypatch: pytest.MonkeyPatch):
    module = _load_audit()
    monkeypatch.setattr(cli, "build_audit", lambda context: payload)
    return module


def _run(audit, monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *args])
    return audit.main()


@pytest.mark.parametrize("mode", ["default", "json", "report", "combined"])
def test_cli_print_modes_keep_exact_serialization(audit, payload, monkeypatch, capsys, mode):
    matrix = audit.render_matrix_json(payload)
    report = audit.render_report(payload)
    args, expected = {
        "default": ([], json.dumps(payload["counts"], sort_keys=True) + "\n"),
        "json": (["--print-json"], matrix),
        "report": (["--print-report"], report),
        "combined": (["--print-json", "--print-report"], matrix + report),
    }[mode]
    assert _run(audit, monkeypatch, *args) == 0
    output = capsys.readouterr()
    assert output.out == expected
    assert output.err == ""


@pytest.mark.parametrize("mode", ["json", "report"])
def test_cli_chunks_reassemble_full_output_and_allow_empty_tail(audit, payload, monkeypatch, capsys, mode):
    content = audit.render_matrix_json(payload) if mode == "json" else audit.render_report(payload)
    size = 2000
    chunks = []
    for index in range(len(content.splitlines()) // size + 2):
        assert _run(audit, monkeypatch, f"--print-{mode}-chunk", str(index), "--chunk-lines", str(size)) == 0
        output = capsys.readouterr()
        assert output.err == ""
        chunks.append(output.out)
    assert "".join(chunks) == content
    assert chunks[-1] == ""


def test_cli_combined_chunk_order_is_json_then_report(audit, payload, monkeypatch, capsys):
    assert _run(
        audit, monkeypatch, "--print-report-chunk", "1", "--print-json-chunk", "1", "--chunk-lines", "7",
    ) == 0
    expected = "".join(
        "\n".join(content.splitlines()[7:14]) + "\n"
        for content in (audit.render_matrix_json(payload), audit.render_report(payload))
    )
    assert capsys.readouterr().out == expected


def test_cli_write_and_check_use_current_script_output_paths(audit, payload, tmp_path, monkeypatch, capsys):
    matrix = tmp_path / "matrix.json"
    report = tmp_path / "report.md"
    monkeypatch.setattr(audit, "MATRIX_PATH", matrix)
    monkeypatch.setattr(audit, "REPORT_PATH", report)
    monkeypatch.setattr(audit, "_rel", lambda path: path.relative_to(tmp_path).as_posix())

    assert _run(audit, monkeypatch, "--check") == 1
    assert capsys.readouterr().out == "missing: matrix.json\nmissing: report.md\n"
    assert not matrix.exists() and not report.exists()

    assert _run(audit, monkeypatch, "--write") == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"written": ["matrix.json", "report.md"], "counts": payload["counts"]}
    assert matrix.read_bytes() == audit.render_matrix_json(payload).encode()
    assert report.read_bytes() == audit.render_report(payload).encode()
    assert audit.check_committed_outputs(payload) == []

    assert _run(audit, monkeypatch, "--check") == 0
    assert capsys.readouterr().out == json.dumps(payload["counts"], sort_keys=True) + "\n"
    matrix.write_text("stale\n", encoding="utf-8")
    assert _run(audit, monkeypatch, "--check") == 1
    assert capsys.readouterr().out == "stale: matrix.json\n"
    assert matrix.read_text() == "stale\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--print-json-chunk", "-1"], "chunk index must be >= 0"),
        (["--print-report-chunk", "0", "--chunk-lines", "0"], "chunk_lines must be > 0"),
        (["--print-json-chunk", "0", "--chunk-lines", "-3"], "chunk_lines must be > 0"),
    ],
)
def test_cli_invalid_chunks_keep_existing_value_errors(audit, monkeypatch, capsys, args, message):
    with pytest.raises(ValueError, match=message):
        _run(audit, monkeypatch, *args)
    assert capsys.readouterr().out == ""


def test_cli_write_and_check_remain_mutually_exclusive(audit, monkeypatch, capsys):
    with pytest.raises(SystemExit) as error:
        _run(audit, monkeypatch, "--check", "--write")
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "not allowed with argument --check" in output.err


@pytest.mark.parametrize("cwd_kind", ["repository", "unrelated"])
def test_standalone_script_finds_repository_with_isolated_python(cwd_kind, tmp_path, payload):
    run = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--check"],
        cwd=ROOT if cwd_kind == "repository" else tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout == json.dumps(payload["counts"], sort_keys=True) + "\n"
    assert run.stderr == ""
