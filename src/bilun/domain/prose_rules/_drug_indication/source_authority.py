"""Deterministic source-version admission. Observation bounds are not legal dates.

No network or wall clock is consulted by a claim evaluation. An independently
reviewed, immutable catalog may admit an explicit forward-continuity window.
Unknown history, uncovered dates and source drift fail closed before predicates.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator
import polars as pl

from ...constants import _GAZETTE_DIR
from ...sut.source_authority_schema import ClinicalSourceAuthorityEvidence

_CATALOG = _GAZETTE_DIR / "source_authority" / "clinical_versions.json"
_ROOT = _GAZETTE_DIR.parents[1]
_ISO = r"^\d{4}-\d{2}-\d{2}$"
_HASH = r"^[0-9a-f]{64}$"
_REFRESH = ("Review the official SGK SUT listing, Gazette daily issue/supplements and relevant "
            "amendments; verify the pinned clinical scope and admit a reviewed source version "
            "for this service date. Do not change the claim date or assume current payment eligibility.")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode='before')
    @classmethod
    def exact_discriminators(cls, value):
        if isinstance(value, dict):
            if 'schema_version' in value and type(value['schema_version']) is not int:
                raise ValueError('Source schema version must be an integer')
            for name in ('positive_currentness_evidence','no_affecting_clinical_amendment_found'):
                if name in value and type(value[name]) is not bool:
                    raise ValueError('Source admission flags must be actual booleans')
        return value


class EvidenceFile(_Strict):
    path: str = Field(min_length=1, max_length=300)
    sha256: str = Field(pattern=_HASH)

    @model_validator(mode="after")
    def safe_path(self):
        path = Path(self.path)
        if path.is_absolute() or ".." in path.parts or not self.path.startswith("data/gazette/"):
            raise ValueError("Evidence must be repository-local gazette data")
        return self


class OfficialReview(_Strict):
    review_id: str = Field(min_length=1, max_length=120)
    checked_at: str
    checked_through: str = Field(pattern=_ISO)
    scope: Literal["named_clinical_report_checks_only"]
    positive_currentness_evidence: Literal[True]
    receipt: EvidenceFile
    evidence: list[EvidenceFile] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_time(self):
        observed = datetime.fromisoformat(self.checked_at.replace("Z", "+00:00"))
        if observed.tzinfo is None or date.fromisoformat(self.checked_through) > observed.astimezone(ZoneInfo('Europe/Istanbul')).date():
            raise ValueError("Review cannot admit a future day or omit its observation timezone")
        return self


class OfficialObservation(_Strict):
    kind: Literal['sgk_sut_listing', 'gazette_daily_contents', 'gazette_supplement_index', 'relevant_amendments']
    source_url: str = Field(pattern=r'^https://(?:www\.)?(?:sgk\.gov\.tr|resmigazete\.gov\.tr)/')
    observed_at: str
    capture: EvidenceFile


class SourceReviewReceipt(_Strict):
    schema_version: Literal[1]
    review_id: str
    checked_at: str
    checked_through: str = Field(pattern=_ISO)
    scope: Literal['named_clinical_report_checks_only']
    named_families: list[str] = Field(min_length=1)
    no_affecting_clinical_amendment_found: Literal[True]
    excluded_dependencies: list[str] = Field(min_length=1)
    observations: list[OfficialObservation] = Field(min_length=4)

    @model_validator(mode='after')
    def positive_complete_observations(self):
        required = {'sgk_sut_listing','gazette_daily_contents','gazette_supplement_index','relevant_amendments'}
        if {row.kind for row in self.observations} != required:
            raise ValueError('Positive official currentness requires every source category')
        checked = datetime.fromisoformat(self.checked_at.replace('Z','+00:00'))
        if checked.tzinfo is None:
            raise ValueError('Review timezone required')
        for row in self.observations:
            observed = datetime.fromisoformat(row.observed_at.replace('Z','+00:00'))
            if (observed.tzinfo is None or observed > checked
                    or observed.astimezone(ZoneInfo('Europe/Istanbul')).date().isoformat() != self.checked_through):
                raise ValueError('All positive source observations must cover the admitted review day')
        return self


class AdmissionWindow(_Strict):
    start: str = Field(pattern=_ISO)
    through: str = Field(pattern=_ISO)
    basis: Literal["established_history", "observed_snapshot", "reviewed_continuity"]
    review_id: str | None = None
    observed_source_sha256: str | None = Field(default=None, pattern=_HASH)

    @model_validator(mode="after")
    def ordered(self):
        start, end = date.fromisoformat(self.start), date.fromisoformat(self.through)
        if start > end or (self.basis == "observed_snapshot" and start != end):
            raise ValueError("Invalid source admission window")
        if (self.basis == "reviewed_continuity") != bool(self.review_id):
            raise ValueError("Continuity alone requires an explicit official review")
        if (self.basis == "observed_snapshot") != bool(self.observed_source_sha256):
            raise ValueError("Observation points must identify their actual document")
        return self


class SourceVersion(_Strict):
    family_id: str = Field(min_length=1, max_length=80)
    version_id: str = Field(min_length=1, max_length=120)
    source_observed_on: str = Field(pattern=_ISO)
    source_docx_sha256: str = Field(pattern=_HASH)
    legal_effective_from: str | None = Field(pattern=_ISO)
    lower_bound_basis: str = Field(min_length=1)
    known_successor_from: str | None = Field(pattern=_ISO)
    evidence: EvidenceFile
    historical_evidence: list[EvidenceFile] = Field(default_factory=list)
    windows: list[AdmissionWindow] = Field(min_length=1)

    @model_validator(mode="after")
    def coherent_windows(self):
        observed = date.fromisoformat(self.source_observed_on)
        if self.legal_effective_from is not None:
            date.fromisoformat(self.legal_effective_from)
        if self.known_successor_from is not None:
            date.fromisoformat(self.known_successor_from)
        windows = sorted(self.windows, key=lambda x: x.start)
        for index, window in enumerate(windows):
            if index and windows[index - 1].through >= window.start:
                raise ValueError("Overlapping admission windows are ambiguous")
            if window.basis == "reviewed_continuity" and date.fromisoformat(window.start) < observed:
                raise ValueError("A current-source review cannot fill unknown past history")
            if window.basis == "established_history" and self.legal_effective_from is None:
                raise ValueError("Unknown historical start cannot become an established interval")
            if window.basis == 'established_history' and (
                    window.start < self.legal_effective_from or date.fromisoformat(window.through) > observed):
                raise ValueError('Established history cannot precede its legal bound or extend past observation')
        return self


class ClauseBinding(_Strict):
    source_ref: str = Field(min_length=1)
    clause_coordinate: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    in_force_text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=_HASH)
    context_anchor: bool = False


class SourceBindings(_Strict):
    schema_version: Literal[1]
    source_docx_sha256: str = Field(pattern=_HASH)
    source_observed_on: str = Field(pattern=_ISO)
    source_url: str = Field(pattern=r"^https://www\.sgk\.gov\.tr/")
    permitted_family_versions: dict[str, str] = Field(min_length=1)
    established_history_from: dict[str, str | None] = Field(min_length=1)
    bindings: list[ClauseBinding] = Field(min_length=1)

    @model_validator(mode="after")
    def distinct_content(self):
        from scripts.sut.prose.clause_identity import normalize_for_hash
        date.fromisoformat(self.source_observed_on)
        if set(self.permitted_family_versions) != set(self.established_history_from):
            raise ValueError('Every bound family requires an explicit historical authority declaration')
        for value in self.established_history_from.values():
            if value is not None:
                date.fromisoformat(value)
        if len({row.source_ref for row in self.bindings}) != len(self.bindings):
            raise ValueError("Duplicate source binding")
        for row in self.bindings:
            if "#" not in row.source_ref or hashlib.sha256(normalize_for_hash(row.in_force_text).encode()).hexdigest() != row.text_sha256:
                raise ValueError("Source reference/text hash must be content-pinned")
        return self


class AuthorityCatalog(_Strict):
    schema_version: Literal[1]
    verification_status: Literal["ai_generated_pending_review"]
    scope: Literal["named_clinical_report_checks_only"]
    deployed_source_corpus_sha256: str = Field(pattern=_HASH)
    legacy_unchanged_modes: list[Literal["non_mecasermin_gh_heading_lower_bound_without_reviewed_upper_bound"]]
    official_reviews: list[OfficialReview] = Field(min_length=1)
    versions: list[SourceVersion] = Field(min_length=1)

    @model_validator(mode="after")
    def unambiguous(self):
        reviews = {row.review_id: row for row in self.official_reviews}
        if len(reviews) != len(self.official_reviews):
            raise ValueError("Duplicate official review")
        if len({row.family_id for row in self.versions}) != len(self.versions):
            raise ValueError("Duplicate/ambiguous clinical family authority")
        for version in self.versions:
            for window in version.windows:
                if window.basis == "reviewed_continuity":
                    review = reviews.get(window.review_id)
                    if review is None or window.through > review.checked_through:
                        raise ValueError("Continuity exceeds its reviewed source evidence")
        return self


def _read_evidence(item: EvidenceFile) -> bytes:
    payload = (_ROOT / item.path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != item.sha256:
        raise ValueError("Pinned source evidence changed")
    return payload


@lru_cache(maxsize=1)
def _parse_catalog(payload: str) -> AuthorityCatalog:
    return AuthorityCatalog.model_validate_json(payload)


def load_source_authority() -> AuthorityCatalog:
    """Re-read/hash deployed assets each time; cache parsing by exact catalog bytes only."""
    catalog = _parse_catalog(_CATALOG.read_text(encoding="utf-8"))
    corpus = _ROOT/'data/gazette/sut_clauses.parquet'
    if hashlib.sha256(corpus.read_bytes()).hexdigest() != catalog.deployed_source_corpus_sha256:
        raise ValueError('Deployed source corpus is missing or differs from its reviewed artifact')
    reviewed_families = {}
    for review in catalog.official_reviews:
        receipt = SourceReviewReceipt.model_validate_json(_read_evidence(review.receipt))
        if any(getattr(receipt, field) != getattr(review, field) for field in
               ('review_id','checked_at','checked_through','scope')):
            raise ValueError('Admission date does not match its pinned official review receipt')
        for observation in receipt.observations:
            _read_evidence(observation.capture)
        reviewed_families[review.review_id] = set(receipt.named_families)
        for item in review.evidence:
            _read_evidence(item)
    for version in catalog.versions:
        binding = SourceBindings.model_validate_json(_read_evidence(version.evidence))
        if (binding.permitted_family_versions.get(version.family_id) != version.version_id
                or binding.established_history_from.get(version.family_id) != version.legal_effective_from
                or binding.source_observed_on != version.source_observed_on):
            raise ValueError('Source evidence is not bound to this family/version/date contract')
        observed_documents = {(version.source_observed_on, version.source_docx_sha256)}
        for item in version.historical_evidence:
            historical = json.loads(_read_evidence(item))
            observed_documents.update((row.get('authoritative_document_as_of'), row.get('docx_sha256'))
                                      for row in historical.get('sources', []) if isinstance(row, dict))
        for window in version.windows:
            if window.basis == 'observed_snapshot' and (window.start, window.observed_source_sha256) not in observed_documents:
                raise ValueError('Observation point/document lacks pinned historical evidence')
            if window.review_id and version.family_id not in reviewed_families[window.review_id]:
                raise ValueError('Official review did not admit this clinical family')
    return catalog


@lru_cache(maxsize=1)
def _parse_corpus(payload: bytes) -> pl.DataFrame:
    """Parse the exact checked bytes; approved renewal never reuses a stale frame."""
    return pl.read_parquet(io.BytesIO(payload))


def _source_matches(version: SourceVersion, corpus_sha256: str | None = None) -> bool:
    from scripts.sut.prose.clause_identity import normalize_for_hash, resolve_gate_b_ref_to_clause_ids

    evidence = SourceBindings.model_validate_json(_read_evidence(version.evidence))
    if (evidence.source_docx_sha256 != version.source_docx_sha256
            or evidence.permitted_family_versions.get(version.family_id) != version.version_id
            or evidence.established_history_from.get(version.family_id) != version.legal_effective_from
            or evidence.source_observed_on != version.source_observed_on):
        return False
    expected = corpus_sha256 or load_source_authority().deployed_source_corpus_sha256
    corpus_bytes = (_ROOT/'data/gazette/sut_clauses.parquet').read_bytes()
    if hashlib.sha256(corpus_bytes).hexdigest() != expected:
        return False
    frame = _parse_corpus(corpus_bytes)
    for binding in evidence.bindings:
        if binding.context_anchor:
            ids = frame.filter((pl.col("clause_key") == binding.source_ref)
                               & pl.col("is_in_force"))["clause_id"].to_list()
        else:
            ids = resolve_gate_b_ref_to_clause_ids(binding.source_ref, frame, encode_eligible_only=False)
        if len(ids) != 1:
            return False
        rows = frame.filter(pl.col("clause_id") == ids[0]).to_dicts()
        if len(rows) != 1:
            return False
        row = rows[0]
        actual = hashlib.sha256(normalize_for_hash(row["in_force_text"]).encode()).hexdigest()
        if (actual != binding.text_sha256 or row["section_id"] != binding.section_id
                or row["clause_coordinate"] != binding.clause_coordinate or row["is_in_force"] is not True):
            return False
    return bool(evidence.bindings)


def resolve_source_authority(family_id: str, service_date) -> ClinicalSourceAuthorityEvidence:
    """Select an admitted source window; never convert source absence into clinical denial."""
    service = service_date if type(service_date) is date else None
    if service is None and isinstance(service_date, str) and re.fullmatch(_ISO, service_date):
        try:
            service = date.fromisoformat(service_date)
        except ValueError:
            pass
    payload = dict(status="review_required", reason="source_authority_unavailable", family_id=family_id,
                   service_date=service.isoformat() if service else None, next_action=_REFRESH)
    try:
        catalog = load_source_authority()
        version = next(row for row in catalog.versions if row.family_id == family_id)
        latest = max(version.windows, key=lambda row: row.through)
        review = next((row for row in catalog.official_reviews if row.review_id == latest.review_id), None)
        payload.update(version_id=version.version_id, legal_effective_from=version.legal_effective_from,
                       source_observed_on=version.source_observed_on, source_docx_sha256=version.source_docx_sha256,
                       admitted_from=latest.start, admitted_through=latest.through,
                       official_review_checked_at=review.checked_at if review else None,
                       review_id=review.review_id if review else None)
        if service is None:
            payload.update(reason="missing_service_date", next_action="Provide the actual service date; today is never substituted.")
        elif version.known_successor_from and service.isoformat() >= version.known_successor_from:
            payload.update(reason="known_successor")
        elif not _source_matches(version, catalog.deployed_source_corpus_sha256):
            payload.update(reason="source_content_changed")
        else:
            window = next((row for row in version.windows if row.start <= service.isoformat() <= row.through), None)
            if window is None:
                payload.update(reason="uncovered_service_date")
            else:
                payload.update(status="admitted", reason="covered", admission_basis=window.basis,
                               admitted_from=window.start, admitted_through=window.through,
                               next_action="Only the named necessary clinical/report checks are source-admitted; remaining reimbursement conditions still require review.")
                if window.basis == "reviewed_continuity":
                    review = next(row for row in catalog.official_reviews if row.review_id == window.review_id)
                    payload.update(review_id=review.review_id, official_review_checked_at=review.checked_at)
                if window.basis == "observed_snapshot":
                    payload.update(source_observed_on=window.start, source_docx_sha256=window.observed_source_sha256)
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, pl.exceptions.PolarsError):
        pass
    return ClinicalSourceAuthorityEvidence(**payload)
