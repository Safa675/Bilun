"""SUT claim data-source mode resolution and provenance metadata."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SYNTHETIC_SUT_DIR = PROJECT_ROOT / "data" / "synthetic" / "sut"
DEFAULT_SYNTHETIC_CLAIMS_DIR = SYNTHETIC_SUT_DIR / "claims"
DEFAULT_SYNTHETIC_CLEAN_DIR = SYNTHETIC_SUT_DIR / "clean"

BILUN_DATA_MODE_ENV = "BILUN_DATA_MODE"
BILUN_CLAIMS_DIR_ENV = "BILUN_CLAIMS_DIR"
BILUN_CLEAN_DIR_ENV = "BILUN_CLEAN_DIR"

_SUT_DATA_MODE_ENV = "SUT_DATA_MODE"
_SUT_CLAIMS_DIR_ENV = "SUT_CLAIMS_DIR"
_SUT_CLEAN_DIR_ENV = "SUT_CLEAN_DIR"

SYNTHETIC_DEMO_MODE = "synthetic_demo"
REAL_CLAIMS_MODE = "real_claims"
VALID_SUT_DATA_MODES = frozenset({SYNTHETIC_DEMO_MODE, REAL_CLAIMS_MODE})


class SUTDataSourceConfigError(ValueError):
    """Raised when SUT data-source mode/path configuration is unsafe."""

    def __init__(self, errors: str | Sequence[str]) -> None:
        self.errors = (errors,) if isinstance(errors, str) else tuple(errors)
        message = "SUT data-source configuration failed"
        if self.errors:
            message = f"{message}: " + "; ".join(self.errors)
        super().__init__(message)


@dataclass(frozen=True)
class SUTDataSourceMetadata:
    """Serializable provenance metadata for SUT claim and clinical inputs."""

    mode: str
    label: str
    claim_source: str
    clinical_source: str | None
    is_synthetic: bool
    notice: str

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "label": self.label,
            "claim_source": self.claim_source,
            "clinical_source": self.clinical_source,
            "is_synthetic": self.is_synthetic,
            "notice": self.notice,
        }


@dataclass(frozen=True)
class SUTDataSourceConfig:
    """Resolved SUT data-source directories and provenance metadata."""

    mode: str
    claims_dir: Path
    clean_dir: Path | None
    metadata: SUTDataSourceMetadata


def resolve_sut_data_source(
    *,
    mode: str | None = None,
    claims_dir: str | Path | None = None,
    clean_dir: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    require_claims_dir: bool = True,
    require_clean_dir: bool = True,
) -> SUTDataSourceConfig:
    """Resolve and validate SUT data-source mode and directories.

    ``synthetic_demo`` safely defaults to the committed synthetic SUT fixture.
    ``real_claims`` never defaults to a real path; deployments must provide
    explicit claim and clinical directories through args or environment.
    """

    env = os.environ if environ is None else environ
    resolved_mode = _resolve_mode(mode, env)
    errors: list[str] = []

    bilun_claims_dir = env.get(BILUN_CLAIMS_DIR_ENV)
    if bilun_claims_dir is None:
        bilun_claims_dir = env.get(_SUT_CLAIMS_DIR_ENV)
        if bilun_claims_dir is not None:
            warnings.warn(
                "SUT_* env vars are deprecated; use BILUN_* instead",
                DeprecationWarning,
                stacklevel=2,
            )
    raw_claims_dir = _coalesce_path(claims_dir, bilun_claims_dir)

    bilun_clean_dir = env.get(BILUN_CLEAN_DIR_ENV)
    if bilun_clean_dir is None:
        bilun_clean_dir = env.get(_SUT_CLEAN_DIR_ENV)
        if bilun_clean_dir is not None:
            warnings.warn(
                "SUT_* env vars are deprecated; use BILUN_* instead",
                DeprecationWarning,
                stacklevel=2,
            )
    raw_clean_dir = _coalesce_path(clean_dir, bilun_clean_dir)

    if resolved_mode == SYNTHETIC_DEMO_MODE:
        resolved_claims_dir = raw_claims_dir or DEFAULT_SYNTHETIC_CLAIMS_DIR
        resolved_clean_dir = raw_clean_dir or DEFAULT_SYNTHETIC_CLEAN_DIR
    elif resolved_mode == REAL_CLAIMS_MODE:
        if raw_claims_dir is None:
            errors.append(
                "real_claims requires BILUN_CLAIMS_DIR (or deprecated SUT_CLAIMS_DIR) "
                "or an explicit claims_dir"
            )
            resolved_claims_dir = Path()
        else:
            resolved_claims_dir = raw_claims_dir
        if raw_clean_dir is None:
            if require_clean_dir:
                errors.append(
                    "real_claims requires BILUN_CLEAN_DIR (or deprecated SUT_CLEAN_DIR) "
                    "or an explicit clean_dir"
                )
            resolved_clean_dir = None
        else:
            resolved_clean_dir = raw_clean_dir
    else:
        raise SUTDataSourceConfigError(
            f"Unsupported BILUN_DATA_MODE (or deprecated SUT_DATA_MODE) '{resolved_mode}'. "
            f"Expected one of: {sorted(VALID_SUT_DATA_MODES)}"
        )

    if resolved_mode == SYNTHETIC_DEMO_MODE:
        _validate_synthetic_path("BILUN_CLAIMS_DIR", resolved_claims_dir, errors)
        if resolved_clean_dir is not None:
            _validate_synthetic_path("BILUN_CLEAN_DIR", resolved_clean_dir, errors)
    elif resolved_mode == REAL_CLAIMS_MODE:
        _validate_real_path("BILUN_CLAIMS_DIR", resolved_claims_dir, errors)
        if resolved_clean_dir is not None:
            _validate_real_path("BILUN_CLEAN_DIR", resolved_clean_dir, errors)

    if require_claims_dir:
        _validate_existing_dir("BILUN_CLAIMS_DIR", resolved_claims_dir, errors)
    if require_clean_dir and resolved_clean_dir is not None:
        _validate_existing_dir("BILUN_CLEAN_DIR", resolved_clean_dir, errors)

    if errors:
        raise SUTDataSourceConfigError(errors)

    metadata = _build_metadata(resolved_mode, resolved_claims_dir, resolved_clean_dir)
    return SUTDataSourceConfig(
        mode=resolved_mode,
        claims_dir=resolved_claims_dir,
        clean_dir=resolved_clean_dir,
        metadata=metadata,
    )


def resolve_sut_claims_dir(
    *,
    mode: str | None = None,
    claims_dir: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve only the claim-line directory for loader callers."""

    return resolve_sut_data_source(
        mode=mode,
        claims_dir=claims_dir,
        environ=environ,
        require_clean_dir=False,
    ).claims_dir


def _resolve_mode(mode: str | None, env: Mapping[str, str]) -> str:
    if mode is not None:
        raw_mode = mode
    else:
        raw_mode = env.get(BILUN_DATA_MODE_ENV)
        if raw_mode is None:
            raw_mode = env.get(_SUT_DATA_MODE_ENV)
            if raw_mode is not None:
                warnings.warn(
                    "SUT_* env vars are deprecated; use BILUN_* instead",
                    DeprecationWarning,
                    stacklevel=3,
                )
    resolved_mode = (raw_mode or SYNTHETIC_DEMO_MODE).strip()
    if resolved_mode not in VALID_SUT_DATA_MODES:
        raise SUTDataSourceConfigError(
            f"Unsupported BILUN_DATA_MODE (or deprecated SUT_DATA_MODE) '{resolved_mode}'. "
            f"Expected one of: {sorted(VALID_SUT_DATA_MODES)}"
        )
    return resolved_mode


def _coalesce_path(explicit: str | Path | None, env_value: str | None) -> Path | None:
    value = explicit if explicit is not None else env_value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _validate_synthetic_path(name: str, path: Path, errors: list[str]) -> None:
    if not _is_under(path, SYNTHETIC_SUT_DIR):
        errors.append(f"{name} must be under data/synthetic/sut for synthetic_demo mode: {path}")


def _validate_real_path(name: str, path: Path, errors: list[str]) -> None:
    if "synthetic" in path.as_posix().lower():
        errors.append(f"{name} must not contain 'synthetic' for real_claims mode: {path}")


def _validate_existing_dir(name: str, path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"{name} directory does not exist: {path}")
    elif not path.is_dir():
        errors.append(f"{name} is not a directory: {path}")


def _is_under(path: Path, ancestor: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(ancestor.resolve(strict=False))
    except ValueError:
        return False
    return True


def _build_metadata(mode: str, claims_dir: Path, clean_dir: Path | None) -> SUTDataSourceMetadata:
    if mode == SYNTHETIC_DEMO_MODE:
        return SUTDataSourceMetadata(
            mode=mode,
            label="Synthetic SUT demo claim data",
            claim_source=_display_path(claims_dir),
            clinical_source=_display_path(clean_dir) if clean_dir is not None else None,
            is_synthetic=True,
            notice="Demo data only. Rule calculations are exact for these synthetic claim lines.",
        )
    return SUTDataSourceMetadata(
        mode=mode,
        label="Hospital claim data",
        claim_source=_display_path(claims_dir),
        clinical_source=_display_path(clean_dir) if clean_dir is not None else None,
        is_synthetic=False,
        notice="Hospital billing claim-line exports supplied by deployment configuration.",
    )


def _display_path(path: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve(strict=False)).as_posix()
    except ValueError:
        return resolved.as_posix()
