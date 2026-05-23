"""Unit tests for SUT data-source mode configuration."""

from __future__ import annotations

import shutil

import pytest

from src.bilun.domain.claims import (
    DEFAULT_SYNTHETIC_CLAIMS_DIR,
    DEFAULT_SYNTHETIC_CLEAN_DIR,
    SUTDataSourceConfigError,
    load_sut_claim_dataset,
    resolve_sut_data_source,
)

pytestmark = pytest.mark.unit


def test_resolves_valid_synthetic_demo_defaults_with_provenance():
    config = resolve_sut_data_source(environ={})

    assert config.mode == "synthetic_demo"
    assert config.claims_dir == DEFAULT_SYNTHETIC_CLAIMS_DIR
    assert config.clean_dir == DEFAULT_SYNTHETIC_CLEAN_DIR
    assert config.metadata.as_dict() == {
        "mode": "synthetic_demo",
        "label": "Synthetic SUT demo claim data",
        "claim_source": "data/synthetic/sut/claims",
        "clinical_source": "data/synthetic/sut/clean",
        "is_synthetic": True,
        "notice": "Demo data only. Rule calculations are exact for these synthetic claim lines.",
    }


def test_resolves_relative_synthetic_paths_from_environment():
    config = resolve_sut_data_source(
        environ={
            "BILUN_DATA_MODE": "synthetic_demo",
            "BILUN_CLAIMS_DIR": "data/synthetic/sut/claims",
            "BILUN_CLEAN_DIR": "data/synthetic/sut/clean",
        }
    )

    assert config.claims_dir == DEFAULT_SYNTHETIC_CLAIMS_DIR
    assert config.clean_dir == DEFAULT_SYNTHETIC_CLEAN_DIR


def test_resolves_valid_real_claims_mode_with_explicit_dirs(tmp_path):
    claims_dir = tmp_path / "real_claims"
    clean_dir = tmp_path / "real_clean"
    claims_dir.mkdir()
    clean_dir.mkdir()

    config = resolve_sut_data_source(
        mode="real_claims",
        claims_dir=claims_dir,
        clean_dir=clean_dir,
        environ={},
    )

    assert config.mode == "real_claims"
    assert config.claims_dir == claims_dir
    assert config.clean_dir == clean_dir
    assert config.metadata.mode == "real_claims"
    assert config.metadata.label == "Hospital claim data"
    assert config.metadata.is_synthetic is False
    assert "synthetic" not in config.metadata.claim_source


def test_resolves_mode_and_paths_from_environment(tmp_path):
    claims_dir = tmp_path / "real_env_claims"
    clean_dir = tmp_path / "real_env_clean"
    claims_dir.mkdir()
    clean_dir.mkdir()

    config = resolve_sut_data_source(
        environ={
            "BILUN_DATA_MODE": "real_claims",
            "BILUN_CLAIMS_DIR": str(claims_dir),
            "BILUN_CLEAN_DIR": str(clean_dir),
        }
    )

    assert config.mode == "real_claims"
    assert config.claims_dir == claims_dir
    assert config.clean_dir == clean_dir


def test_rejects_invalid_sut_data_mode():
    with pytest.raises(SUTDataSourceConfigError) as exc_info:
        resolve_sut_data_source(mode="estimated_demo", environ={})

    assert "Unsupported SUT_DATA_MODE 'estimated_demo'" in str(exc_info.value)


def test_rejects_synthetic_demo_mode_outside_synthetic_sut_paths(tmp_path):
    claims_dir = tmp_path / "demo_claims"
    clean_dir = tmp_path / "demo_clean"
    claims_dir.mkdir()
    clean_dir.mkdir()

    with pytest.raises(SUTDataSourceConfigError) as exc_info:
        resolve_sut_data_source(
            mode="synthetic_demo",
            claims_dir=claims_dir,
            clean_dir=clean_dir,
            environ={},
        )

    message = str(exc_info.value)
    assert "BILUN_CLAIMS_DIR must be under data/synthetic/sut for synthetic_demo mode" in message
    assert "BILUN_CLEAN_DIR must be under data/synthetic/sut for synthetic_demo mode" in message


def test_rejects_missing_claim_and_clean_directories(tmp_path):
    with pytest.raises(SUTDataSourceConfigError) as exc_info:
        resolve_sut_data_source(
            mode="real_claims",
            claims_dir=tmp_path / "missing_claims",
            clean_dir=tmp_path / "missing_clean",
            environ={},
        )

    message = str(exc_info.value)
    assert "BILUN_CLAIMS_DIR directory does not exist" in message
    assert "BILUN_CLEAN_DIR directory does not exist" in message


def test_rejects_real_claims_mode_without_directory_specification():
    with pytest.raises(SUTDataSourceConfigError) as exc_info:
        resolve_sut_data_source(mode="real_claims", environ={})

    message = str(exc_info.value)
    assert "real_claims requires SUT_CLAIMS_DIR or an explicit claims_dir" in message
    assert "real_claims requires SUT_CLEAN_DIR or an explicit clean_dir" in message


def test_rejects_real_claims_mode_pointing_at_synthetic_paths():
    with pytest.raises(SUTDataSourceConfigError) as exc_info:
        resolve_sut_data_source(
            mode="real_claims",
            claims_dir=DEFAULT_SYNTHETIC_CLAIMS_DIR,
            clean_dir=DEFAULT_SYNTHETIC_CLEAN_DIR,
            environ={},
        )

    message = str(exc_info.value)
    assert "BILUN_CLAIMS_DIR must not contain 'synthetic' for real_claims mode" in message
    assert "BILUN_CLEAN_DIR must not contain 'synthetic' for real_claims mode" in message


def test_loader_accepts_configured_synthetic_claims_dir():
    dataset = load_sut_claim_dataset(
        claims_dir=DEFAULT_SYNTHETIC_CLAIMS_DIR,
        mode="synthetic_demo",
    )

    assert len(dataset.claims) == 138
    assert len(dataset.patient_totals) == 50


def test_loader_rejects_real_claims_mode_with_synthetic_claims_dir():
    with pytest.raises(SUTDataSourceConfigError) as exc_info:
        load_sut_claim_dataset(
            claims_dir=DEFAULT_SYNTHETIC_CLAIMS_DIR,
            mode="real_claims",
        )

    assert "must not contain 'synthetic' for real_claims mode" in str(exc_info.value)


def test_loader_can_read_configured_real_claims_dir(tmp_path):
    claims_dir = tmp_path / "real_claims"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)

    dataset = load_sut_claim_dataset(claims_dir=claims_dir, mode="real_claims")

    assert len(dataset.claims) == 138
    assert len(dataset.patient_totals) == 50
