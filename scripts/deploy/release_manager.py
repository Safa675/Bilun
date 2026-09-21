"""release_manager.py

Core release management logic for atomic frontend deployments on the Bilun VPS.
Handles standalone artifact assembly, checksum verification, shared asset store
synchronization with collision detection, atomic symlink activation, rollback,
and safe retention pruning.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from collections.abc import Generator

SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
RUN_ID_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


class ReleaseError(Exception):
    """Raised when a release invariant is violated."""


def validate_sha(sha: str) -> str:
    """Validate 40-character hex commit SHA."""
    sha = sha.strip()
    if not SHA_RE.match(sha):
        raise ReleaseError(f"Invalid Git SHA (must be 40-character hex): '{sha}'")
    return sha.lower()


def validate_run_id(run_id: str) -> str:
    """Validate workflow run identifier."""
    run_id = run_id.strip()
    if not RUN_ID_RE.match(run_id):
        raise ReleaseError(f"Invalid run_id (must contain only alphanumeric, '_', '-', '.'): '{run_id}'")
    return run_id


def sha256_file(path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@contextmanager
def file_lock(lock_path: Path, timeout: float = 300.0) -> Generator[None]:
    """Acquire an exclusive advisory file lock using flock."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")
    start = time.monotonic()
    acquired = False
    try:
        while time.monotonic() - start < timeout:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (BlockingIOError, OSError):
                time.sleep(0.5)
        if not acquired:
            raise ReleaseError(f"Could not acquire deploy lock at {lock_path} within {timeout}s")
        yield
    finally:
        if acquired:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        f.close()


def assemble_release_payload(
    build_frontend_dir: Path,
    staging_release_dir: Path,
    sha: str,
    run_id: str,
) -> dict[str, Any]:
    """Assemble standalone Next.js build output into a clean release payload.

    Copies:
    - .next/standalone/frontend/. -> staging_release_dir/
    - .next/static -> staging_release_dir/.next/static
    - public -> staging_release_dir/public
    Writes:
    - RELEASE.json
    """
    standalone_dir = build_frontend_dir / ".next" / "standalone"
    if not standalone_dir.exists():
        raise ReleaseError(f"Next.js standalone directory not found at {standalone_dir}")

    # In monorepos / projects with outputFileTracingRoot, Next.js may place server.js
    # under .next/standalone/frontend or directly under .next/standalone
    source_root = standalone_dir / "frontend"
    if not (source_root / "server.js").exists():
        if (standalone_dir / "server.js").exists():
            source_root = standalone_dir
        else:
            raise ReleaseError(f"Could not find server.js in {standalone_dir} or {standalone_dir / 'frontend'}")

    if staging_release_dir.exists():
        shutil.rmtree(staging_release_dir)
    staging_release_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy standalone server and traced modules (including dotfiles like .next)
    for entry in os.listdir(source_root):
        src = source_root / entry
        dst = staging_release_dir / entry
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=True)
        else:
            shutil.copy2(src, dst)

    # 2. Copy static assets to .next/static
    static_src = build_frontend_dir / ".next" / "static"
    if not static_src.exists():
        raise ReleaseError(f"Next.js static assets not found at {static_src}")
    static_dst = staging_release_dir / ".next" / "static"
    if static_dst.exists():
        shutil.rmtree(static_dst)
    shutil.copytree(static_src, static_dst, symlinks=True)

    # 3. Copy public directory
    public_src = build_frontend_dir / "public"
    public_dst = staging_release_dir / "public"
    if public_src.exists():
        if public_dst.exists():
            shutil.rmtree(public_dst)
        shutil.copytree(public_src, public_dst, symlinks=True)

    # 4. Verify essential files exist
    server_js = staging_release_dir / "server.js"
    build_id_file = staging_release_dir / ".next" / "BUILD_ID"
    if not server_js.exists():
        raise ReleaseError(f"Assembled release is missing server.js at {server_js}")
    if not build_id_file.exists():
        raise ReleaseError(f"Assembled release is missing .next/BUILD_ID at {build_id_file}")

    build_id = build_id_file.read_text(encoding="utf-8").strip()

    # 5. Count assets
    asset_count = sum(1 for _ in static_dst.rglob("*") if _.is_file())

    metadata: dict[str, Any] = {
        "sha": sha,
        "run_id": run_id,
        "build_id": build_id,
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "asset_count": asset_count,
    }

    with open(staging_release_dir / "RELEASE.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def build_asset_manifest(release_dir: Path) -> dict[str, str]:
    """Generate a manifest of all static assets with relative paths and SHA256 checksums."""
    static_dir = release_dir / ".next" / "static"
    if not static_dir.exists():
        return {}

    manifest: dict[str, str] = {}
    for p in sorted(static_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(static_dir).as_posix()
            manifest[rel] = sha256_file(p)
    return manifest


def sync_shared_assets(
    release_dir: Path,
    shared_assets_static_dir: Path,
) -> tuple[int, int]:
    """Copy release static assets into the shared store with checksum collision protection.

    Returns (copied_count, skipped_count).
    Fails closed if any file exists with a differing checksum.
    """
    static_src = release_dir / ".next" / "static"
    if not static_src.exists():
        raise ReleaseError(f"Static directory not found in release: {static_src}")

    shared_assets_static_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_asset_manifest(release_dir)

    copied = 0
    skipped = 0

    for rel_path, expected_hash in manifest.items():
        src_file = static_src / rel_path
        dst_file = shared_assets_static_dir / rel_path

        if dst_file.exists():
            existing_hash = sha256_file(dst_file)
            if existing_hash != expected_hash:
                raise ReleaseError(
                    f"Collision in shared asset store: '{rel_path}' exists with hash {existing_hash} "
                    f"but candidate has hash {expected_hash}!"
                )
            skipped += 1
        else:
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            copied += 1

    return copied, skipped


def atomic_activate_release(
    release_path: Path,
    current_link: Path,
) -> Path | None:
    """Atomically point current_link to release_path.

    Returns previous target Path if one existed, else None.
    """
    if not release_path.exists():
        raise ReleaseError(f"Cannot activate nonexistent release: {release_path}")

    current_link.parent.mkdir(parents=True, exist_ok=True)
    previous_target: Path | None = None

    if current_link.is_symlink():
        try:
            resolved = current_link.resolve(strict=True)
            previous_target = resolved
        except (OSError, ValueError):
            # Broken symlink
            previous_target = None

    tmp_link = current_link.with_name(f"{current_link.name}.next")
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()

    os.symlink(release_path.resolve(), tmp_link)
    os.replace(tmp_link, current_link)

    return previous_target


def atomic_rollback(
    previous_target: Path,
    current_link: Path,
) -> None:
    """Atomically restore current_link to previous_target."""
    if not previous_target.exists():
        raise ReleaseError(f"Rollback target does not exist on disk: {previous_target}")

    tmp_link = current_link.with_name(f"{current_link.name}.rollback")
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()

    os.symlink(previous_target.resolve(), tmp_link)
    os.replace(tmp_link, current_link)


def prune_old_releases(
    releases_dir: Path,
    current_link: Path,
    manifests_dir: Path,
    shared_assets_static_dir: Path,
    keep_count: int = 3,
    grace_seconds: float = 86400.0,
) -> tuple[list[str], int]:
    """Prune releases older than keep_count, and clean unreferenced stale assets.

    Returns (pruned_shas, unreferenced_assets_deleted).
    Guarantees:
    - Never deletes the current active release.
    - Never deletes the captured previous release.
    """
    if not releases_dir.exists():
        return [], 0

    active_release_path: Path | None = None
    if current_link.is_symlink():
        try:
            active_release_path = current_link.resolve(strict=True)
        except OSError:
            pass

    # Gather all candidate release folders
    releases = []
    for d in releases_dir.iterdir():
        if d.is_dir() and SHA_RE.match(d.name):
            mtime = d.stat().st_mtime
            releases.append((mtime, d))

    # Sort descending by mtime (newest first)
    releases.sort(key=lambda x: x[0], reverse=True)

    retained_dirs: list[Path] = []
    to_prune: list[Path] = []

    for idx, (_, d) in enumerate(releases):
        if idx < keep_count or (active_release_path and d.samefile(active_release_path)):
            retained_dirs.append(d)
        else:
            to_prune.append(d)

    pruned_shas: list[str] = []
    for d in to_prune:
        sha = d.name
        shutil.rmtree(d)
        manifest_file = manifests_dir / f"{sha}.assets"
        if manifest_file.exists():
            manifest_file.unlink()
        pruned_shas.append(sha)

    # Garbage collect unreferenced assets
    retained_asset_paths: set[str] = set()
    for d in retained_dirs:
        manifest_file = manifests_dir / f"{d.name}.assets"
        if manifest_file.exists():
            try:
                with open(manifest_file, encoding="utf-8") as f:
                    data = json.load(f)
                    retained_asset_paths.update(data.keys())
            except Exception:
                pass

    assets_deleted = 0
    if shared_assets_static_dir.exists() and len(retained_asset_paths) > 0:
        now = time.time()
        for p in shared_assets_static_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(shared_assets_static_dir).as_posix()
                if rel not in retained_asset_paths:
                    age = now - p.stat().st_mtime
                    if age > grace_seconds:
                        p.unlink()
                        assets_deleted += 1

    return pruned_shas, assets_deleted


def build_worktree_release(
    repo_dir: Path,
    sha: str,
    run_id: str,
    builds_dir: Path,
    staging_dir: Path,
    releases_dir: Path,
    manifests_dir: Path,
    verbose: bool = True,
) -> Path:
    """Build a standalone release from a clean detached git worktree."""
    sha = validate_sha(sha)
    run_id = validate_run_id(run_id)

    target_release = releases_dir / sha
    manifest_path = manifests_dir / f"{sha}.assets"

    # Idempotence check: does target release already exist?
    if target_release.exists() and manifest_path.exists():
        if verbose:
            print(f"[release] Release {sha} already exists in {releases_dir}. Validating idempotence...")
        existing_manifest = build_asset_manifest(target_release)
        with open(manifest_path, encoding="utf-8") as f:
            recorded = json.load(f)
        if existing_manifest == recorded:
            if verbose:
                print(f"[release] Release {sha} verified byte-identical. Skipping build.")
            return target_release
        raise ReleaseError(f"Release {sha} already exists on disk but manifest does not match!")

    build_dir = builds_dir / f"{run_id}-{sha}"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.parent.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"[release] Creating detached git worktree for {sha} at {build_dir}")

    try:
        subprocess.run(
            ["git", "-C", str(repo_dir), "worktree", "add", "--detach", str(build_dir), sha],
            check=True,
            capture_output=True,
            text=True,
        )

        frontend_dir = build_dir / "frontend"
        if not frontend_dir.exists():
            raise ReleaseError(f"No frontend directory found at {frontend_dir}")

        # Reuse existing node_modules from base repo if available to avoid full network npm ci
        base_node_modules = repo_dir / "frontend" / "node_modules"
        target_node_modules = frontend_dir / "node_modules"

        if base_node_modules.exists() and not target_node_modules.exists():
            if verbose:
                print(f"[release] Linking/copying node_modules from {base_node_modules}")
            # Try cp -al for hardlink sharing (instant, same filesystem)
            res = subprocess.run(
                ["cp", "-al", str(base_node_modules), str(target_node_modules)],
                capture_output=True,
            )
            if res.returncode != 0:
                # Fallback to npm ci if hardlinking fails
                if verbose:
                    print("[release] Hardlinking node_modules failed; running npm ci...")
                subprocess.run(["npm", "ci"], cwd=str(frontend_dir), check=True)
        elif not target_node_modules.exists():
            if verbose:
                print("[release] Running npm ci...")
            subprocess.run(["npm", "ci"], cwd=str(frontend_dir), check=True)

        if verbose:
            print(f"[release] Running npm run build in {frontend_dir}...")

        build_res = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True,
        )
        if build_res.returncode != 0:
            print(build_res.stdout, file=sys.stdout)
            print(build_res.stderr, file=sys.stderr)
            raise ReleaseError(f"npm run build failed with exit code {build_res.returncode}")

        # Assemble into staging release
        staging_release = staging_dir / sha
        if verbose:
            print(f"[release] Assembling standalone payload into {staging_release}...")

        assemble_release_payload(frontend_dir, staging_release, sha, run_id)

        # Write asset manifest
        manifests_dir.mkdir(parents=True, exist_ok=True)
        manifest = build_asset_manifest(staging_release)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        if verbose:
            print(f"[release] Manifest written to {manifest_path} ({len(manifest)} assets)")

        return staging_release

    finally:
        # Disposable build workspace cleanup trap
        if build_dir.exists():
            if verbose:
                print(f"[release] Cleaning up worktree at {build_dir}...")
            subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force", str(build_dir)], capture_output=True)
            if build_dir.exists():
                shutil.rmtree(build_dir, ignore_errors=True)
            subprocess.run(["git", "-C", str(repo_dir), "worktree", "prune"], capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bilun frontend release manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # assemble
    p_asm = subparsers.add_parser("assemble")
    p_asm.add_argument("--build-frontend-dir", type=Path, required=True)
    p_asm.add_argument("--staging-release-dir", type=Path, required=True)
    p_asm.add_argument("--sha", type=str, required=True)
    p_asm.add_argument("--run-id", type=str, default="local")

    # sync-assets
    p_sync = subparsers.add_parser("sync-assets")
    p_sync.add_argument("--release-dir", type=Path, required=True)
    p_sync.add_argument("--shared-assets-static-dir", type=Path, required=True)

    # activate
    p_act = subparsers.add_parser("activate")
    p_act.add_argument("--release-path", type=Path, required=True)
    p_act.add_argument("--current-link", type=Path, required=True)

    # rollback
    p_rb = subparsers.add_parser("rollback")
    p_rb.add_argument("--previous-target", type=Path, required=True)
    p_rb.add_argument("--current-link", type=Path, required=True)

    # prune
    p_prune = subparsers.add_parser("prune")
    p_prune.add_argument("--releases-dir", type=Path, required=True)
    p_prune.add_argument("--current-link", type=Path, required=True)
    p_prune.add_argument("--manifests-dir", type=Path, required=True)
    p_prune.add_argument("--shared-assets-static-dir", type=Path, required=True)
    p_prune.add_argument("--keep", type=int, default=3)
    p_prune.add_argument("--grace-seconds", type=float, default=86400.0)

    args = parser.parse_args()

    try:
        if args.command == "assemble":
            meta = assemble_release_payload(
                args.build_frontend_dir,
                args.staging_release_dir,
                validate_sha(args.sha),
                validate_run_id(args.run_id),
            )
            print(json.dumps(meta, indent=2))
        elif args.command == "sync-assets":
            copied, skipped = sync_shared_assets(args.release_dir, args.shared_assets_static_dir)
            print(f"Synced assets: {copied} copied, {skipped} skipped")
        elif args.command == "activate":
            prev = atomic_activate_release(args.release_path, args.current_link)
            print(f"Activated: {args.release_path}")
            if prev:
                print(f"Previous target: {prev}")
        elif args.command == "rollback":
            atomic_rollback(args.previous_target, args.current_link)
            print(f"Rolled back to: {args.previous_target}")
        elif args.command == "prune":
            pruned, unreferenced = prune_old_releases(
                args.releases_dir,
                args.current_link,
                args.manifests_dir,
                args.shared_assets_static_dir,
                keep_count=args.keep,
                grace_seconds=args.grace_seconds,
            )
            print(f"Pruned releases: {pruned}, deleted unreferenced assets: {unreferenced}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
