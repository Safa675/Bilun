"""Necessary SMA safety restrictions, SUT replacement effective 2025-05-06.

These are not the complete initiation/maintenance eligibility rules. In
particular, an absent diagnosis code never certifies absent medical history.
"""
from datetime import date
from typing import Any

from ...claims.clinical_evidence import SmaEvidence, parse_clinical_evidence
from .clinical_common import Predicate, Reader, all_of, result, scope_missing
from .matching import _drug_name_matches

SOURCE_REFS = [
    '4.2.49.(2)#d31c4d8c', '4.2.49.(3)#88014037',
    '4.2.49.(4)#d9c6cd1d', '4.2.49.(5)#597ea9c2',
]


def evaluate_sma_safety(line: Any) -> dict[str, Any]:
    evidence = parse_clinical_evidence(line.sma_evidence, SmaEvidence)
    reader = Reader(evidence, 'sma_evidence')
    date_missing = scope_missing(evidence, 'sma_evidence', line.drug_claim_date,
                                 date(2025, 5, 6), date(2026, 10, 2))
    if date_missing:
        return result('sma_safety_2025', reader, Predicate(None), SOURCE_REFS,
                      date_missing=date_missing)
    shared = all_of(reader.bool('hypoxic_ischemic_encephalopathy', False),
                    reader.bool('hypoxic_birth_neurological_sequelae', False))
    sources = ['4.2.49.(5)#597ea9c2']
    if _drug_name_matches(line.drug_name, ['nusinersen', 'nusinersen sodium']):
        shared = all_of(shared,
            reader.bool('brain_spinal_history_impeding_procedure', False),
            reader.bool('csf_shunt_or_catheter', False),
            reader.bool('bacterial_meningitis_history', False),
            reader.bool('viral_encephalitis_history', False))
        sources = list(SOURCE_REFS)
        if reader.get('sma_type') in ('type_2', 'type_3'):
            shared = all_of(shared, reader.bool('lumbar_puncture_suitability_documented'))
            sources.append('4.2.49.B.e#927a1a83@within:4.2.49.B#1a8f10e4')
        elif reader.get('sma_type') not in ('type_1', 'newborn_screening'):
            shared = all_of(shared, Predicate(None, ('sma_evidence.sma_type',)))
    return result('sma_safety_2025', reader, shared, sources)
