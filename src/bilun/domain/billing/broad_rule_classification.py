"""Reviewed meaning/proof policy over already evaluated broad rules.

Construct one classifier per report and pass the adapters' ownership-bearing
legacy rows. No engine or predicate runs here. Raw rows remain historical;
only a separately proven adverse outcome can produce an unpriced finding.
The deployment's policy/corpora are immutable; a new version needs a restart.
Request validation must separately gate supplied-field provenance, including
raw nonmatches: this layer cannot certify defaults invented by a dict adapter.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Any

import polars as pl

from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.billing.rule_findings import RuleEvaluation, RuleFinding, build_finding_id
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.constants import SUT_CLAUSES_PATH, _GAZETTE_DIR, _PROSE_RULES_DIR
from src.bilun.domain.prose_rules.dental_2_4_1 import _normalize_tr

_POLICY_PATH = _GAZETTE_DIR / "broad_rule_classification_policy.json"
_POLICY_SHA256 = "f3f107828e5cebd41749ad43b98288fc56fc2ba045dc8b43859a21ee139087c4"
_PRECIOUS = "2.4.1.(1).precious_metal_no_pay"
_LOAD_LOCK = RLock()


@dataclass(frozen=True)
class BroadRulePolicy:
    rule_id: str
    family: str
    authored_meaning: str
    matched_surface: str
    authored_verification_status: str
    gates: tuple[str, ...]
    source_file: str
    source_locators: tuple[str, ...]
    fatura_inceleme_ref: str | None


@dataclass(frozen=True)
class _DentalProof:
    clause_key: str
    text_sha256: str
    verified_versions: tuple[str, ...]
    official_docx_sha256: tuple[str, ...]
    official_announcements: tuple[str, ...]
    source_named_materials: frozenset[str]


@dataclass(frozen=True)
class SourceApplicabilityAttestation:
    """Output of the separate release source review, never a clock inference.

    The producer must attest amendment completeness and applicability over the
    service interval. This classifier can verify its identity and scope, not
    conduct that legal/source review. Do not synthesize this from claim fields.
    Accept review_evidence_id/source_manifest_sha256 only from that trusted
    release attestation producer, never request JSON. Their shape checks below
    do not validate provenance, signatures, or contents of the review artifact.
    """

    clause_text_sha256: str
    official_docx_sha256: str
    service_date_from: date
    service_date_through: date
    review_evidence_id: str
    source_manifest_sha256: str

    def __post_init__(self) -> None:
        for digest in (
            self.clause_text_sha256,
            self.official_docx_sha256,
            self.source_manifest_sha256,
        ):
            if len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
                raise ValueError("Source attestation requires full evidence digests")
        if not self.review_evidence_id.strip() or (
            type(self.service_date_from) is not date
            or type(self.service_date_through) is not date
            or self.service_date_from > self.service_date_through
        ):
            raise ValueError("Source attestation requires a reviewed service interval")


def _name(value: str) -> str:
    return " ".join(_normalize_tr(value).split())


@lru_cache(maxsize=4)
def _load_policy(
    path: Path, corpus_dir: Path
) -> tuple[Mapping[str, BroadRulePolicy], _DentalProof]:
    blob = path.read_bytes()
    if sha256(blob).hexdigest() != _POLICY_SHA256:
        raise ValueError("Reviewed broad classification policy digest changed")
    payload = json.loads(blob)
    catalog = load_broad_rule_catalog(prose_rules_dir=corpus_dir)
    authored = {
        row.source_file: json.loads((corpus_dir / Path(row.source_file).name).read_text())
        for row in {r.source_file: r for r in catalog}.values()
    }
    entries: dict[str, BroadRulePolicy] = {}
    for rule, source in zip(payload["rules"], catalog, strict=True):
        if (rule["rule_id"], rule["family"]) != (source.rule_id, source.family):
            raise ValueError("Classification policy/catalog identity mismatch")
        corpus = authored[source.source_file]
        raw = corpus["rules"][source.family_rule_index]
        frozen = {
            "family": source.family,
            "source_file": source.source_file,
            "effective_date": corpus.get("effective_date"),
            "rule": raw,
        }
        digest = sha256(
            json.dumps(frozen, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if digest != rule["authored_sha256"]:
            raise ValueError(f"Reviewed authored rule digest changed: {source.rule_id}")
        entries[source.rule_id] = BroadRulePolicy(
            rule_id=source.rule_id,
            family=source.family,
            authored_meaning=rule["authored_meaning"],
            matched_surface=rule["matched_surface"],
            authored_verification_status=rule["authored_verification_status"],
            gates=tuple(rule["gates"]),
            source_file=source.source_file,
            source_locators=source.source_locators,
            fatura_inceleme_ref=source.fatura_inceleme_ref,
        )
    proof = payload["dental_source_proof"]
    return MappingProxyType(entries), _DentalProof(
        clause_key=proof["clause_key"],
        text_sha256=proof["text_sha256"],
        verified_versions=tuple(proof["reviewed_snapshot_versions"]),
        official_docx_sha256=tuple(proof["official_docx_sha256"]),
        official_announcements=tuple(proof["official_announcements"]),
        source_named_materials=frozenset(_name(x) for x in proof["source_named_materials"]),
    )


def load_broad_classification_policy(
    *,
    policy_path: Path | None = None,
    prose_rules_dir: Path | None = None,
) -> Mapping[str, BroadRulePolicy]:
    """Load the reviewed immutable matrix once; reject any unreviewed drift."""
    with _LOAD_LOCK:
        return _load_policy(policy_path or _POLICY_PATH, prose_rules_dir or _PROSE_RULES_DIR)[0]


class _SourceUnavailable(ValueError):
    pass


_DENTAL_SOURCE_CACHE: dict[tuple[str, _DentalProof], str] = {}


def _dental_source(content: bytes, proof: _DentalProof) -> str:
    """Hash every promotion's bytes; cache successes only and parse those bytes."""
    key = (sha256(content).hexdigest(), proof)
    with _LOAD_LOCK:
        if key in _DENTAL_SOURCE_CACHE:
            return _DENTAL_SOURCE_CACHE[key]
        try:
            rows = (
                pl.read_parquet(BytesIO(content))
                .filter(pl.col("clause_key") == proof.clause_key)
                .to_dicts()
            )
        except (OSError, pl.exceptions.PolarsError) as exc:
            raise _SourceUnavailable("effective_source_unavailable") from exc
        if len(rows) != 1:
            raise _SourceUnavailable("effective_source_missing_or_ambiguous")
        row = rows[0]
        text = row.get("in_force_text")
        if (
            row.get("is_in_force") is not True
            or row.get("is_heading") is not False
            or row.get("is_amendment") is not False
            or row.get("is_superseded_marker") is not False
            or row.get("source_effective_date") not in proof.verified_versions
            or not isinstance(text, str)
            or sha256(text.encode()).hexdigest() != proof.text_sha256
        ):
            raise _SourceUnavailable("effective_source_proof_changed")
        clause_id = str(row["clause_id"])
        _DENTAL_SOURCE_CACHE.clear()
        _DENTAL_SOURCE_CACHE[key] = clause_id
        return clause_id


@dataclass(frozen=True)
class BroadRuleDisposition:
    evaluation: RuleEvaluation
    disposition: str
    reason: str | None
    policy: BroadRulePolicy
    source_authority: str
    source_status: str
    legacy_row: dict[str, Any] | None
    finding: RuleFinding | None = None


@dataclass(frozen=True)
class BroadRuleClassifier:
    """Read-only indexes for a report; classify each existing observation once."""

    ctx: PatientClaimContext
    applicability: SourceApplicabilityAttestation | None = None
    _headers: Mapping = field(init=False, repr=False)
    _materials: Mapping = field(init=False, repr=False)
    _procedures: Mapping = field(init=False, repr=False)
    _policy: Mapping[str, BroadRulePolicy] = field(init=False, repr=False)
    _proof: _DentalProof = field(init=False, repr=False)

    def __post_init__(self) -> None:
        ctx = self.ctx
        if not ctx.patient_id.strip():
            raise ValueError("Classification requires an actual patient identity")
        headers = {row.claim_id: row for row in ctx.claims}
        if len(headers) != len(ctx.claims) or any(not key.strip() for key in headers):
            raise ValueError("Duplicate or blank classification claim identity")
        groups = (
            (ctx.claims, "claim_id"),
            (ctx.material_lines, "material_line_id"),
            (ctx.procedure_lines, "procedure_line_id"),
            (ctx.drug_lines, "drug_claim_line_id"),
            (ctx.diagnoses, "diagnosis_id"),
            (ctx.performed_procedure_lines, "performed_line_id"),
            (ctx.medula_rejection_events, "rejection_event_id"),
        )
        for rows, key in groups:
            identities = [(row.claim_id, getattr(row, key)) for row in rows]
            if len(set(identities)) != len(identities) or any(not x[1].strip() for x in identities):
                raise ValueError("Duplicate or blank classification source identity")
            if any(row.patient_id != ctx.patient_id or row.claim_id not in headers for row in rows):
                raise ValueError("Classification source does not belong to patient/claim")
        for key, value in (
            ("_headers", headers),
            ("_materials", {(r.claim_id, r.material_line_id): r for r in ctx.material_lines}),
            ("_procedures", {(r.claim_id, r.procedure_line_id): r for r in ctx.procedure_lines}),
        ):
            object.__setattr__(self, key, MappingProxyType(value))
        with _LOAD_LOCK:
            matrix, proof = _load_policy(_POLICY_PATH, _PROSE_RULES_DIR)
        object.__setattr__(self, "_policy", matrix)
        object.__setattr__(self, "_proof", proof)

    def classify(self, evaluation: RuleEvaluation, legacy_row: Any | None) -> BroadRuleDisposition:
        """Accept an adapter's scoped legacy-row object, never an unscoped dict."""
        policy = self._policy.get(evaluation.rule_id)
        if policy is None:
            raise ValueError(f"Unknown broad rule: {evaluation.rule_id}")
        if evaluation.patient_id != self.ctx.patient_id or (
            evaluation.claim_id not in self._headers
            and not (evaluation.claim_id is None and not self._headers)
        ):
            raise ValueError("Observation belongs to another patient/claim")
        dental = policy.family == "dental_2_4_1"
        if evaluation.line_kind == "material":
            if not dental or (evaluation.claim_id, evaluation.line_id) not in self._materials:
                raise ValueError("Observation references a foreign source material")
        elif evaluation.line_kind != "claim" or (
            dental
            and (
                evaluation.evaluation_status == "evaluated"
                or any(claim_id == evaluation.claim_id for claim_id, _ in self._materials)
            )
        ):
            raise ValueError("Observation has incorrect claim/line scope")
        raw = None
        if legacy_row is not None:
            for key in ("patient_id", "claim_id", "rule_id"):
                if getattr(legacy_row, key, None) != getattr(evaluation, key):
                    raise ValueError(f"Legacy observation {key} mismatch")
            if getattr(legacy_row, "family", policy.family) != policy.family:
                raise ValueError("Legacy observation family mismatch")
            if dental and getattr(legacy_row, "material_line_id", None) != evaluation.line_id:
                raise ValueError("Legacy observation source material mismatch")
            raw = deepcopy(legacy_row.legacy_row)
            if raw.get("rule_id") != evaluation.rule_id:
                raise ValueError("Legacy payload rule mismatch")
        if evaluation.evaluation_status == "evaluated":
            if evaluation.claim_id is None:
                raise ValueError("An evaluated observation requires an actual claim")
            if evaluation.decision not in ("matched", "not_matched"):
                raise ValueError("Evaluated observation needs a predicate decision")
            if (evaluation.decision == "matched") != (raw is not None):
                raise ValueError("Predicate decision and legacy row disagree")
        elif evaluation.evaluation_status not in ("missing_inputs", "unavailable"):
            raise ValueError("Unknown observation evaluation status")

        def result(
            disposition, reason=None, *, source_status="authored_locator_unverified", finding=None
        ):
            return BroadRuleDisposition(
                evaluation,
                disposition,
                reason,
                policy,
                "sgk_fatura_guideline_sut_takes_precedence"
                if policy.family == "fatura_inceleme_prose"
                else "sut_authored_reference",
                source_status,
                raw,
                finding,
            )

        if evaluation.evaluation_status != "evaluated":
            return result(evaluation.evaluation_status, evaluation.reason)
        if evaluation.decision == "not_matched":
            return result("not_matched")
        if policy.authored_verification_status == "ai_generated_pending_review":
            return result("review_only", "authored_source_pending_independent_review")
        if policy.matched_surface == "withheld_adverse":
            return result("unavailable", policy.gates[0])
        if policy.matched_surface != "dental_precious_metal_proof":
            return result(policy.matched_surface, policy.gates[0])
        return self._classify_precious(evaluation, raw, result)

    def _classify_precious(self, evaluation, raw, result):
        if evaluation.rule_id != _PRECIOUS:
            raise ValueError("Unknown source-proven adverse rule")
        header = self._headers[evaluation.claim_id]
        material = self._materials[evaluation.claim_id, evaluation.line_id]
        if header.scenario_tag == "validate_claim_adapter":
            return result("unavailable", "request_field_provenance_unavailable")
        procedure = self._procedures.get((evaluation.claim_id, material.procedure_line_id))
        if procedure is None or procedure.procedure_category != "dental_restoration":
            return result("unavailable", "authoritative_dental_category_and_line_link_required")
        if _name(material.material_name) not in self._proof.source_named_materials:
            return result(
                "review_only", "exact_source_named_material_or_verified_composition_required"
            )
        if raw.get("material_name") != material.material_name:
            raise ValueError("Legacy payload material name differs from observed source line")
        try:
            charge = Decimal(str(material.billed_amount_try))
        except (InvalidOperation, ValueError):
            return result("unavailable", "actual_line_charge_unavailable")
        if not charge.is_finite():
            return result("unavailable", "actual_line_charge_unavailable")
        if charge <= 0:
            return result("not_applicable", "no_positive_actual_line_charge")
        attestation = self.applicability
        if attestation is None or (
            attestation.clause_text_sha256 != self._proof.text_sha256
            or attestation.official_docx_sha256 not in self._proof.official_docx_sha256
        ):
            return result("unavailable", "source_version_applicability_required")
        for service_date in (material.material_date, procedure.procedure_date):
            if type(service_date) is not date or not (
                attestation.service_date_from <= service_date <= attestation.service_date_through
            ):
                return result("unavailable", "source_version_applicability_required")
        try:
            clause_id = _dental_source(SUT_CLAUSES_PATH.read_bytes(), self._proof)
        except (OSError, _SourceUnavailable) as exc:
            return result(
                "unavailable",
                str(exc) if isinstance(exc, _SourceUnavailable) else "effective_source_unavailable",
            )
        finding = RuleFinding(
            finding_id=build_finding_id(
                rule_id=evaluation.rule_id,
                patient_id=evaluation.patient_id,
                claim_id=evaluation.claim_id,
                line_kind="material",
                line_id=evaluation.line_id,
            ),
            patient_id=evaluation.patient_id,
            claim_id=evaluation.claim_id,
            line_kind="material",
            line_id=evaluation.line_id,
            rule_id=evaluation.rule_id,
            kind=evaluation.rule_id,
            severity="error",
            detail="SUT §2.4.1(1): diş tedavisinde kaynakta adı geçen kıymetli malzeme bedeli ödenmez.",
            sut_section_id="2.4.1",
            regulatory_source={
                "clause_id": clause_id,
                "clause_key": self._proof.clause_key,
                "text_sha256": self._proof.text_sha256,
                "official_announcements": list(self._proof.official_announcements),
                "verified_service_date_from": attestation.service_date_from.isoformat(),
                "verified_service_date_through": attestation.service_date_through.isoformat(),
                "applicability_review_evidence_id": attestation.review_evidence_id,
                "source_manifest_sha256": attestation.source_manifest_sha256,
                "official_docx_sha256": attestation.official_docx_sha256,
            },
            source_engine="dental_2_4_1",
            evaluation_status="evaluated",
            required_inputs=list(
                dict.fromkeys(
                    evaluation.required_inputs
                    + [
                        "material_line_id",
                        "procedure_line_id",
                        "billed_amount_try",
                        "material_date",
                        "procedure_date",
                        "effective_source_proof",
                    ]
                )
            ),
            missing_inputs=[],
        )
        return result(
            "unpriced_compliance",
            source_status="primary_meaning_and_date_verified",
            finding=finding,
        )


def classify_broad_observation(
    evaluation: RuleEvaluation,
    legacy_row: Any | None,
    ctx: PatientClaimContext,
    *,
    applicability: SourceApplicabilityAttestation | None = None,
) -> BroadRuleDisposition:
    """Convenience for one row; report builders should reuse one classifier."""
    return BroadRuleClassifier(ctx, applicability).classify(evaluation, legacy_row)
