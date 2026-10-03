"""Independent actual TypeScript helper to published request/HTTP boundary."""
import json
import subprocess
import shutil
from pathlib import Path

import pytest

from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.api.test_validation_contract_v2 import client, _login  # noqa: F401
from tests.unit.domain.prose_rules.test_report_documentation_completion import CASES, request

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def node_for_ts_helper():
    node = shutil.which("node")
    if not node or "experimental-strip-types" not in subprocess.run(
        [node, "--help"], capture_output=True, text=True, check=True
    ).stdout:
        pytest.skip("Actual TypeScript helper probe needs Node with type stripping")
    return node


@pytest.mark.parametrize("prefix,cls,field,factory,evaluator", CASES)
@pytest.mark.parametrize("fact,status", [(True, "criterion_clear"), (False, "restriction_not_met"), (None, "unknown")])
def test_actual_helper_keeps_report_content_unknown_or_explicit(client, node_for_ts_helper, prefix, cls, field, factory, evaluator, fact, status):  # noqa: F811
    raw = request(prefix, factory, field, fact)
    script = "import {drugMaterialPayload} from './frontend/src/components/tabs/sut/sections/drugInputs.ts';let raw='';for await(const c of process.stdin)raw+=c;const p=JSON.parse(raw);p.materials=p.materials.map(m=>drugMaterialPayload(m,true));process.stdout.write(JSON.stringify(p));"
    output = subprocess.run([node_for_ts_helper, "--experimental-strip-types", "--input-type=module", "-e", script], input=json.dumps(raw), capture_output=True, text=True, check=True, cwd=ROOT)
    payload = json.loads(output.stdout)
    assert payload["materials"][0][prefix][field] is fact
    typed = ClaimValidationRequest.model_validate(payload)
    assert getattr(getattr(typed.materials[0], prefix), field) is fact
    _login(client)
    response = client.post("/api/validate-claim", json=payload, headers={"X-Bilun-Validation-Contract": "2"})
    assert response.status_code == 200, response.text
    body = response.json()
    row = next(r for r in body["advisories"] if r["rule"] == "drug_indication")
    name = "enteral_pediatric_reports_2026" if prefix == "enteral_evidence" else "renal_source_constraints"
    outcome = next(r for r in row["clinical_restrictions"] if r["constraint_set"] == name)
    assert outcome["criterion_status"] == status
    assert (prefix + "." + field in row["missing_inputs"]) is (fact is None)
    assert body["is_valid"] is None and not row["clinical_eligibility_complete"]
    for private in ["NEVER_EXPOSE", "private_note", '"receipts"', '"execution_scope"', '"raw_evidence"']:
        assert private not in response.text


@pytest.mark.parametrize("prefix,cls,field,factory,evaluator", CASES)
def test_actual_disabled_helper_strips_report_evidence(node_for_ts_helper, prefix, cls, field, factory, evaluator):
    raw = request(prefix, factory, field, True)
    script = "import {drugMaterialPayload} from './frontend/src/components/tabs/sut/sections/drugInputs.ts';let raw='';for await(const c of process.stdin)raw+=c;process.stdout.write(JSON.stringify(drugMaterialPayload(JSON.parse(raw),false)));"
    output = subprocess.run([node_for_ts_helper, "--experimental-strip-types", "--input-type=module", "-e", script], input=json.dumps(raw["materials"][0]), capture_output=True, text=True, check=True, cwd=ROOT)
    assert prefix not in json.loads(output.stdout)


@pytest.mark.parametrize("prefix,cls,field,factory,evaluator", CASES)
@pytest.mark.parametrize("fact,status", [(True, "criterion_clear"), (False, "restriction_not_met"), (None, "unknown")])
def test_reviewed_october_three_reaches_report_predicates(client, prefix, cls, field, factory, evaluator, fact, status):  # noqa: F811
    raw = request(prefix, factory, field, fact)
    raw["drug_context"]["service_date"] = "2026-10-03"
    raw["materials"][0][prefix].update(applies_on="2026-10-03", assessment_date="2026-10-03")
    _login(client)
    response = client.post("/api/validate-claim", json=raw, headers={"X-Bilun-Validation-Contract": "2"})
    assert response.status_code == 200, response.text
    body = response.json()
    row = next(r for r in body["advisories"] if r["rule"] == "drug_indication")
    name = "enteral_pediatric_reports_2026" if prefix == "enteral_evidence" else "renal_source_constraints"
    outcome = next(r for r in row["clinical_restrictions"] if r["constraint_set"] == name)
    assert outcome["source_authority"]["status"] == "admitted"
    assert outcome["criterion_status"] == status
    assert any(check["field"] == prefix + "." + field for check in outcome["checks"])
    assert body["is_valid"] is None and not row["clinical_eligibility_complete"]
