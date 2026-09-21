"""tests/unit/deploy/test_frontend_release_lifecycle.py

Automated lifecycle tests for atomic frontend releases:
- Input validation (SHA, run_id)
- Standalone payload assembly and validation
- Shared static asset store synchronization with collision protection
- Atomic symlink activation and rollback
- Retention pruning and unreferenced asset garbage collection
- Concurrency advisory lock
"""

from __future__ import annotations

import json
import os
import time

import pytest

from scripts.deploy.release_manager import (
    ReleaseError,
    assemble_release_payload,
    atomic_activate_release,
    atomic_rollback,
    file_lock,
    prune_old_releases,
    sync_shared_assets,
    validate_run_id,
    validate_sha,
)


def test_validate_sha_valid():
    valid = "a" * 40
    assert validate_sha(valid) == valid
    assert validate_sha("A" * 40) == valid


@pytest.mark.parametrize("bad_sha", [
    "abc",
    "g" * 40,
    "a" * 39,
    "a" * 41,
    "../../etc/passwd",
    "abcde; rm -rf /",
])
def test_validate_sha_invalid(bad_sha: str):
    with pytest.raises(ReleaseError):
        validate_sha(bad_sha)


def test_validate_run_id_valid():
    assert validate_run_id("run-123_abc.4") == "run-123_abc.4"


@pytest.mark.parametrize("bad_id", [
    "../../foo",
    "run/id",
    "run;id",
    "run id",
])
def test_validate_run_id_invalid(bad_id: str):
    with pytest.raises(ReleaseError):
        validate_run_id(bad_id)


def create_mock_next_build(frontend_dir):
    """Create a realistic Next.js standalone build structure."""
    standalone = frontend_dir / ".next" / "standalone" / "frontend"
    standalone.mkdir(parents=True)
    (standalone / "server.js").write_text("console.log('server');", encoding="utf-8")
    (standalone / "package.json").write_text("{}", encoding="utf-8")

    server_dir = standalone / ".next" / "server"
    server_dir.mkdir(parents=True)
    (standalone / ".next" / "BUILD_ID").write_text("build-12345", encoding="utf-8")

    static_dir = frontend_dir / ".next" / "static" / "chunks"
    static_dir.mkdir(parents=True)
    (static_dir / "app-chunk-1.js").write_text("console.log('chunk 1');", encoding="utf-8")
    (static_dir / "app-chunk-2.js").write_text("console.log('chunk 2');", encoding="utf-8")

    public_dir = frontend_dir / "public"
    public_dir.mkdir(parents=True)
    (public_dir / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")


def test_assemble_release_payload(tmp_path):
    frontend_dir = tmp_path / "build_workspace" / "frontend"
    create_mock_next_build(frontend_dir)

    staging_dir = tmp_path / "staging" / "test-release"
    sha = "1" * 40
    run_id = "test-run"

    meta = assemble_release_payload(frontend_dir, staging_dir, sha, run_id)

    assert meta["sha"] == sha
    assert meta["run_id"] == run_id
    assert meta["build_id"] == "build-12345"
    assert meta["asset_count"] == 2

    assert (staging_dir / "server.js").exists()
    assert (staging_dir / ".next" / "BUILD_ID").read_text(encoding="utf-8").strip() == "build-12345"
    assert (staging_dir / ".next" / "static" / "chunks" / "app-chunk-1.js").exists()
    assert (staging_dir / "public" / "favicon.ico").exists()

    release_json = json.loads((staging_dir / "RELEASE.json").read_text(encoding="utf-8"))
    assert release_json["build_id"] == "build-12345"


def test_sync_shared_assets_and_collision_protection(tmp_path):
    frontend_dir = tmp_path / "frontend"
    create_mock_next_build(frontend_dir)
    staging_dir = tmp_path / "staging"
    assemble_release_payload(frontend_dir, staging_dir, "1" * 40, "run1")

    shared_static = tmp_path / "shared" / "_next" / "static"

    # Initial sync
    copied, skipped = sync_shared_assets(staging_dir, shared_static)
    assert copied == 2
    assert skipped == 0
    assert (shared_static / "chunks" / "app-chunk-1.js").exists()

    # Re-syncing same content skips without error (idempotent)
    copied, skipped = sync_shared_assets(staging_dir, shared_static)
    assert copied == 0
    assert skipped == 2

    # Collision test: same file path with DIFFERENT content fails closed
    (shared_static / "chunks" / "app-chunk-1.js").write_text("tampered/differing content", encoding="utf-8")
    with pytest.raises(ReleaseError) as excinfo:
        sync_shared_assets(staging_dir, shared_static)
    assert "Collision in shared asset store" in str(excinfo.value)


def test_atomic_activation_and_rollback(tmp_path):
    releases_dir = tmp_path / "releases"
    releases_dir.mkdir()

    rel_a = releases_dir / ("a" * 40)
    rel_a.mkdir()
    (rel_a / "version.txt").write_text("Release A", encoding="utf-8")

    rel_b = releases_dir / ("b" * 40)
    rel_b.mkdir()
    (rel_b / "version.txt").write_text("Release B", encoding="utf-8")

    current = tmp_path / "current"

    # 1. Activate Release A
    prev = atomic_activate_release(rel_a, current)
    assert prev is None
    assert current.is_symlink()
    assert current.resolve() == rel_a.resolve()
    assert (current / "version.txt").read_text(encoding="utf-8") == "Release A"

    # 2. Activate Release B
    prev = atomic_activate_release(rel_b, current)
    assert prev == rel_a.resolve()
    assert current.resolve() == rel_b.resolve()
    assert (current / "version.txt").read_text(encoding="utf-8") == "Release B"

    # 3. Rollback to Release A
    atomic_rollback(prev, current)
    assert current.resolve() == rel_a.resolve()
    assert (current / "version.txt").read_text(encoding="utf-8") == "Release A"


def test_prune_old_releases_keeps_current_and_cleans_unreferenced_assets(tmp_path):
    releases_dir = tmp_path / "releases"
    manifests_dir = tmp_path / "manifests"
    shared_static = tmp_path / "assets" / "_next" / "static"
    current = tmp_path / "current"

    releases_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)
    shared_static.mkdir(parents=True)

    # Create 5 releases (r1 oldest ... r5 newest) with distinct prefixes
    shas = [f"{i}" * 40 for i in range(1, 6)]
    for idx, sha in enumerate(shas):
        rdir = releases_dir / sha
        rdir.mkdir()
        # Set distinct mtimes
        mtime = 1000.0 + (idx * 100.0)
        os.utime(rdir, (mtime, mtime))

        chunk_name = f"chunk-{sha[:4]}.js"
        manifest_data = {f"chunks/{chunk_name}": "dummyhash"}
        (manifests_dir / f"{sha}.assets").write_text(json.dumps(manifest_data), encoding="utf-8")

        chunk_file = shared_static / "chunks" / chunk_name
        chunk_file.parent.mkdir(parents=True, exist_ok=True)
        chunk_file.write_text(f"content-{sha[:4]}", encoding="utf-8")
        # Set file mtime to 2 days ago so it's older than grace period
        old_mtime = time.time() - 200000
        os.utime(chunk_file, (old_mtime, old_mtime))

    # Activate r4 (newest is r5, active is r4)
    r4 = releases_dir / shas[3]
    atomic_activate_release(r4, current)

    # Prune keeping top 2 releases + active
    pruned, unref_deleted = prune_old_releases(
        releases_dir=releases_dir,
        current_link=current,
        manifests_dir=manifests_dir,
        shared_assets_static_dir=shared_static,
        keep_count=2,
        grace_seconds=86400.0,
    )

    # Out of [r1, r2, r3, r4, r5]:
    # Top 2 by mtime: r5, r4
    # r4 is also active.
    # So r1, r2, r3 should be pruned.
    assert set(pruned) == {shas[0], shas[1], shas[2]}
    assert not (releases_dir / shas[0]).exists()
    assert (releases_dir / shas[3]).exists()  # active
    assert (releases_dir / shas[4]).exists()  # newest

    # Stale unreferenced chunks for r1, r2, r3 should be deleted
    assert not (shared_static / "chunks" / f"chunk-{shas[0][:4]}.js").exists()
    assert not (shared_static / "chunks" / f"chunk-{shas[1][:4]}.js").exists()
    assert not (shared_static / "chunks" / f"chunk-{shas[2][:4]}.js").exists()
    assert (shared_static / "chunks" / f"chunk-{shas[3][:4]}.js").exists()
    assert (shared_static / "chunks" / f"chunk-{shas[4][:4]}.js").exists()
    assert unref_deleted == 3


def test_file_lock_mutual_exclusion(tmp_path):
    lock_file = tmp_path / "deploy.lock"

    with file_lock(lock_file, timeout=1.0):
        # Nested attempt should timeout
        with pytest.raises(ReleaseError):
            with file_lock(lock_file, timeout=0.1):
                pass
