"""Apply source-specific necessary restrictions without certifying payment."""
from typing import Any

from .clinical_sma import evaluate_sma_safety
from .clinical_enteral import evaluate_enteral_reports
from .clinical_ravulizumab import evaluate_ravulizumab_continuation
from .clinical_antifungal import evaluate_antifungal
from .clinical_renal import evaluate_renal
from .matching import _drug_name_matches


def evaluate_clinical_restrictions(line: Any, rules: list[dict[str, Any]], codes: list[str] | None = None, selected_rule_id: str | None = None) -> list[dict[str, Any]]:
    kinds = {r.get('clinical_constraint_set') for r in rules
             if _drug_name_matches(line.drug_name, r.get('drug_names') or [])
             and _drug_name_matches(line.drug_name, r.get('clinical_constraint_drugs') or r.get('drug_names') or [])}
    evaluations = []
    if 'sma_safety_2025' in kinds:
        evaluations.append(evaluate_sma_safety(line))
    if 'antifungal_source_constraints' in kinds:
        evaluations.append(evaluate_antifungal(line))
    if 'renal_source_constraints' in kinds:
        evaluations.append(evaluate_renal(line))
    if 'enteral_pediatric_reports_2026' in kinds:
        item = evaluate_enteral_reports(line, selected_rule_id)
        if item is not None:
            evaluations.append(item)
    if 'ravulizumab_nmosd_continuation_2026' in kinds:
        item = evaluate_ravulizumab_continuation(line, codes)
        if item is not None:
            evaluations.append(item)
    return evaluations


def apply_clinical_restrictions(base: dict[str, Any], line: Any,
                                rules: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = evaluate_clinical_restrictions(line, rules, base.get("observed_icd10_codes"), base.get("selected_rule_id"))
    if not outcomes:
        return base
    merged = dict(base)
    merged['clinical_restrictions'] = outcomes
    merged['clinical_eligibility_complete'] = False
    failed = next((x for x in outcomes if x['criterion_status'] == 'restriction_not_met'), None)
    missing = sorted({m for x in outcomes for m in x['missing_inputs']})
    # Even cleared necessary predicates leave unimplemented source criteria.
    # The review result prevents an empty violation being mistaken for payment.
    if failed is None:
        missing.append('remaining_sut_clinical_criteria')
    existing = base.get('violation')
    # Legacy infection-only ICD routes cannot disprove source-authorized
    # prophylaxis for an underlying malignancy/transplant diagnosis.
    incomplete_icd_route = (existing and existing.get('violation_kind') == 'indication_mismatch'
                            and bool(outcomes))
    # Generic enteral names alone do not establish the distinct dysphagia/
    # thickener supplemental scope. Avoid a manufactured board-report failure.
    unverified_enteral_supplement = (
        existing and existing.get('rule_id') == '4.2.8.A.paediatric_dysphagia_special_enteral_2boxes'
        and any(x['constraint_set'] == 'enteral_pediatric_reports_2026' for x in outcomes)
    )
    dates_supported = all(x['criterion_status'] != 'not_evaluated' for x in outcomes)
    if incomplete_icd_route and failed is None:
        # Preserve the fact that the currently encoded ICD subset did not match,
        # while withholding a denial where new prophylaxis facts/source scope
        # are unresolved. No unrelated diagnosis is promoted into a valid route.
        violation = dict(existing)
        violation['severity'] = 'review'
        violation['message_tr'] = 'Kodlanmış tanı yolları eşleşmedi; kaynakta tanımlı diğer klinik koşullar ayrıca doğrulanmalıdır.'
    elif existing and existing.get('severity') == 'error' and failed is None and not unverified_enteral_supplement and dates_supported:
        violation = dict(existing)
    else:
        source = failed or outcomes[0]
        violation = {
            'drug_claim_line_id': line.drug_claim_line_id,
            'claim_id': line.claim_id, 'drug_name': line.drug_name,
            'drug_code': line.drug_code or None,
            'rule_id': source['constraint_set'],
            'selected_rule_id': source['constraint_set'],
            'sut_section': source.get('sut_section') or ('4.2.49' if source['constraint_set'].startswith('sma_')
                            else '4.2.23' if source['constraint_set'].startswith('antifungal_') else '4.2.9'),
            'violation_kind': 'clinical_restriction_not_met' if failed else 'needs_clinical_verification',
            'severity': 'error' if failed else 'review',
            'message_tr': ('Kaynakta belirtilen klinik kısıt sağlanmıyor; diğer geri ödeme koşulları ayrıca değerlendirilmelidir.'
                           if failed else 'Klinik koşullar ve eksik bilgiler doğrulanmalıdır; bu değerlendirme ödeme uygunluğunu kesinleştirmez.'),
        }
    violation['clinical_restrictions'] = outcomes
    violation['clinical_eligibility_complete'] = False
    violation['missing_inputs'] = sorted(set([*(violation.get('missing_inputs') or []), *missing]))
    violation['required_inputs'] = sorted(set([*(violation.get('required_inputs') or []),
                                               *violation['missing_inputs']]))
    violation['evaluation_status'] = 'missing_inputs' if violation['missing_inputs'] else 'evaluated'
    for key in ('applicability_status', 'observed_icd10_codes', 'matched_icd10_codes',
                'unmatched_icd10_codes', 'eligible_icd10_codes_or_ranges', 'eligible_route_rule_ids'):
        violation[key] = base.get(key)
    merged['selected_rule_id'] = violation.get('selected_rule_id')
    merged['violation'] = violation
    merged['evaluation_status'] = violation['evaluation_status']
    merged['missing_inputs'] = violation['missing_inputs']
    merged['required_inputs'] = violation['required_inputs']
    return merged
