"""Cli for the deterministic rule-surfacing audit."""

from __future__ import annotations

import argparse
import json
from typing import Any
from .model import AuditContext
from .inventory import (
    build_audit,
)
from .render import (
    _render_chunk,
    render_matrix_json,
    render_report,
)


def check_committed_outputs(ctx: AuditContext, audit: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        ctx.matrix_path: render_matrix_json(audit),
        ctx.report_path: render_report(audit),
    }
    for path, content in expected.items():
        if not path.is_file():
            errors.append(f"missing: {ctx.relative_path(path)}")
            continue
        if path.read_text(encoding="utf-8") != content:
            errors.append(f"stale: {ctx.relative_path(path)}")
    return errors


def main(ctx: AuditContext) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify committed outputs without writing")
    mode.add_argument("--write", action="store_true", help="write deterministic committed outputs")
    parser.add_argument("--print-json", action="store_true", help="print the generated matrix JSON")
    parser.add_argument("--print-report", action="store_true", help="print the generated Markdown report")
    parser.add_argument("--print-json-chunk", type=int, help="print one zero-based JSON line chunk")
    parser.add_argument("--print-report-chunk", type=int, help="print one zero-based report line chunk")
    parser.add_argument("--chunk-lines", type=int, default=250, help="lines per bounded output chunk")
    args = parser.parse_args()

    audit = build_audit(ctx)
    if args.print_json:
        print(render_matrix_json(audit), end="")
    if args.print_report:
        print(render_report(audit), end="")
    if args.print_json_chunk is not None:
        print(
            _render_chunk(
                render_matrix_json(audit),
                index=args.print_json_chunk,
                chunk_lines=args.chunk_lines,
            ),
            end="",
        )
    if args.print_report_chunk is not None:
        print(
            _render_chunk(
                render_report(audit),
                index=args.print_report_chunk,
                chunk_lines=args.chunk_lines,
            ),
            end="",
        )
    if args.write:
        outputs = {
            ctx.matrix_path: render_matrix_json(audit),
            ctx.report_path: render_report(audit),
        }
        for path, content in outputs.items():
            path.write_text(content, encoding="utf-8")
        print(json.dumps({"written": sorted(ctx.relative_path(path) for path in outputs), "counts": audit["counts"]}, sort_keys=True))
    if args.check:
        errors = check_committed_outputs(ctx, audit)
        if errors:
            for error in errors:
                print(error)
            return 1
        print(json.dumps(audit["counts"], sort_keys=True))
    if not (
        args.check
        or args.write
        or args.print_json
        or args.print_report
        or args.print_json_chunk is not None
        or args.print_report_chunk is not None
    ):
        print(json.dumps(audit["counts"], sort_keys=True))
    return 0
