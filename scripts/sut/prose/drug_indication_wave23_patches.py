"""DEPRECATED (Track B1): SOURCE_PATCHES retired — edit YAML then compile.

This module remains importable so old stage names do not crash, but
SOURCE_PATCHES is empty. Authoritative linkage lives in
``data/gazette/prose_rule_sources/**/*.yaml``.
"""

from __future__ import annotations

SOURCE_PATCHES: dict[str, list[str]] = {}
