"""Generate the public historical archive and seal the finite byte-only profile.

Archive reproduction requires the original reviewed Git objects. CI uses the
strict committed archive instead, without depending on feature branch objects.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import pprint
import re
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSPORT_PATHS = (
    "src/bilun/api/schemas.py",
    "src/bilun/api/routes/billing.py",
    "src/bilun/domain/billing/drug_indication_findings.py",
)
TOOLING_PATHS = (
    "docs/operations/single-vps-wavea-release.md",
    "scripts/deploy/capture_release_preflight.py",
    "scripts/deploy/issue_wavea_activation.py",
    "scripts/deploy/rehearse_wavea_same_port.py",
    "scripts/deploy/verify_final_source_refresh_transition.py",
    "tests/unit/deploy/fixtures/final_source_refresh_mainc44_tooling.json",
    "tests/unit/deploy/fixtures/final_source_refresh_mainf28_tooling.json",
    "tests/unit/deploy/test_final_source_refresh_transition.py",
    "tests/unit/deploy/test_raw_report_transport.py",
    "tests/unit/deploy/test_raw_report_transport_source_profile.py",
    "tests/unit/deploy/test_shared_interpreter_rollback_preflight.py",
    "tests/unit/deploy/test_shared_interpreter_source_profile.py",
)
ARCHIVES = {
    "clinical_baseline": ("3f5540cf199cb464b1fca1d7d7d6ff024d5edc3b", TRANSPORT_PATHS),
    "clinical_candidate": ("3e0e0c6d88fdcd4817e0a7a84b3361184d78b1ea", TRANSPORT_PATHS),
    "shared_interpreter": ("5c89ed53f2545c2d27072d630a46249b31091736", TOOLING_PATHS),
}


def git(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(ROOT), *arguments], check=True, capture_output=True
    ).stdout


def replace_literal(path: Path, name: str, value) -> None:
    source = path.read_text(encoding="utf-8")
    nodes = [
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    ]
    if len(nodes) != 1:
        raise ValueError("Generated literal must exist exactly once: " + name)
    node = nodes[0]
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1 : node.end_lineno] = [
        name + " = " + pprint.pformat(value, width=100, sort_dicts=True) + "\n"
    ]
    path.write_text("".join(lines), encoding="utf-8")


def generate_archives() -> None:
    pinned, groups = {}, {}
    for name, (sha, paths) in ARCHIVES.items():
        tree = git("rev-parse", sha + "^{tree}").decode().strip()
        metadata, sources = {}, {}
        for path in paths:
            entry = git("ls-tree", "-z", sha, "--", path).rstrip(b"\0")
            descriptor, actual_path = entry.split(b"\t")
            mode, kind, blob = descriptor.decode().split()
            if actual_path.decode() != path or (mode, kind) != ("100644", "blob"):
                raise ValueError("Historical archive has an unexpected tree entry")
            body = git("show", f"{sha}:{path}")
            record = {
                "mode": mode,
                "type": kind,
                "blob_sha1": blob,
                "sha256": hashlib.sha256(body).hexdigest(),
                "size_bytes": len(body),
            }
            metadata[path] = record
            encoded = base64.b64encode(zlib.compress(body, 9)).decode()
            sources[path] = {
                **record,
                "zlib_base64_chunks": [
                    encoded[index : index + 76] for index in range(0, len(encoded), 76)
                ],
            }
        pinned[name] = {"source_commit": sha, "source_tree": tree, "sources": metadata}
        groups[name] = {"source_commit": sha, "source_tree": tree, "sources": sources}
    archive = {
        "schema_version": 1,
        "purpose": "Historical public source bytes only; "
        "no authority for later code or deployment.",
        "encoding": "zlib-base64",
        "archives": groups,
    }
    destination = ROOT / "tests/unit/deploy/fixtures/integration_historical_sources.json"
    destination.write_text(json.dumps(archive, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    replace_literal(
        ROOT / "tests/unit/deploy/integration_historical_sources.py", "_PINNED_ARCHIVES", pinned
    )


def seal_profile() -> None:
    import importlib.util

    path = ROOT / "scripts/deploy/verify_integration_byte_profile.py"
    spec = importlib.util.spec_from_file_location("byte_profile_generator_input", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    closure = module.product_closure(ROOT, module.PRODUCT_SHA)
    replace_literal(path, "PRODUCT_CLOSURE_SHA256", hashlib.sha256(closure).hexdigest())
    changed = {
        row.decode()
        for row in git("diff", "--name-only", "-z", module.BASE_SHA, module.PRODUCT_SHA).split(
            b"\0"
        )
        if row
    }
    replace_literal(path, "REVIEWED_CHANGED_PATHS", tuple(sorted(changed | module.TOOLING_PATHS)))
    pins = {
        name: module.disk_entry(ROOT / name)
        for name in sorted(module.TOOLING_PATHS)
        if name != module.VERIFIER_PATH
    }
    replace_literal(path, "REVIEWED_TOOLING", pins)
    source = path.read_bytes()
    slot = re.compile(rb'(?m)^REVIEWED_SELF_SHA256 = "([0-9a-f]{64})"$')
    matches = list(slot.finditer(source))
    if len(matches) != 1:
        raise ValueError("Byte-only verifier self slot is ambiguous")
    start, end = matches[0].span(1)
    digest = hashlib.sha256(source[:start] + b"0" * 64 + source[end:]).hexdigest()
    path.write_bytes(source[:start] + digest.encode() + source[end:])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", action="store_true")
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    if not args.archives and not args.seal:
        parser.error("choose --archives and/or --seal explicitly")
    if args.archives:
        generate_archives()
        print("Generated exact historical public-source archive")
    if args.seal:
        seal_profile()
        print("Sealed finite integration byte-only profile; deployment remains blocked")


if __name__ == "__main__":
    main()
