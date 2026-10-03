"""Necessary SMA safety restrictions, SUT replacement effective 2025-05-06.

These are not the complete initiation/maintenance eligibility rules. In
particular, an absent diagnosis code never certifies absent medical history.
"""
from datetime import date
from typing import Any

from ...claims.clinical_evidence import SmaEvidence, parse_clinical_evidence
from .clinical_common import Predicate, all_of, result, scope_missing
from .runtime_observations import ClinicalObservationCollector, ObservedClinicalReader
from .matching import _drug_name_matches

SOURCE_REFS = [
    '4.2.49.(2)#d31c4d8c', '4.2.49.(3)#88014037',
    '4.2.49.(4)#d9c6cd1d', '4.2.49.(5)#597ea9c2',
]


def evaluate_sma_safety(line: Any, *, observer: ClinicalObservationCollector | None = None) -> dict[str, Any]:
    evidence = parse_clinical_evidence(line.sma_evidence, SmaEvidence)
    reader = ObservedClinicalReader(evidence, 'sma_evidence', observer)
    date_missing = scope_missing(evidence, 'sma_evidence', line.drug_claim_date,
                                 date(2025, 5, 6), date(2026, 10, 2))
    reader.record_source_gate('sma.source_date', date_missing)
    if date_missing:
        return result('sma_safety_2025', reader, Predicate(None), SOURCE_REFS,
                      date_missing=date_missing)
    shared = all_of(reader.bound('sma.shared.no_hypoxic_ischemic_encephalopathy', ['4.2.49.(5)#597ea9c2']).bool('hypoxic_ischemic_encephalopathy', False),
                    reader.bound('sma.shared.no_hypoxic_birth_sequelae', ['4.2.49.(5)#597ea9c2']).bool('hypoxic_birth_neurological_sequelae', False))
    sources = ['4.2.49.(5)#597ea9c2']
    if observer is not None:
        observer.context('drug_name')
    if _drug_name_matches(line.drug_name, ['nusinersen', 'nusinersen sodium']):
        shared = all_of(shared,
            reader.bound('sma.nusinersen.no_impeding_brain_spinal_history', ['4.2.49.(2)#d31c4d8c']).bool('brain_spinal_history_impeding_procedure', False),
            reader.bound('sma.nusinersen.no_csf_shunt_or_catheter', ['4.2.49.(3)#88014037']).bool('csf_shunt_or_catheter', False),
            reader.bound('sma.nusinersen.no_bacterial_meningitis', ['4.2.49.(4)#d9c6cd1d']).bool('bacterial_meningitis_history', False),
            reader.bound('sma.nusinersen.no_viral_encephalitis', ['4.2.49.(4)#d9c6cd1d']).bool('viral_encephalitis_history', False))
        sources = list(SOURCE_REFS)
        reader.record_context('sma_type')
        if reader.get('sma_type') in ('type_2', 'type_3'):
            shared = all_of(shared, reader.bound('sma.nusinersen.lumbar_puncture_suitability', ['4.2.49.B.e#927a1a83@within:4.2.49.B#1a8f10e4']).bool('lumbar_puncture_suitability_documented'))
            sources.append('4.2.49.B.e#927a1a83@within:4.2.49.B#1a8f10e4')
        elif reader.get('sma_type') not in ('type_1', 'newborn_screening'):
            shared = all_of(shared, Predicate(None, ('sma_evidence.sma_type',)))
            if observer is not None:
                observer.route('sma.nusinersen.type', 'blocked_inputs', ['missing_sma_type'],
                               ['sma_evidence.sma_type'])
        elif observer is not None:
            observer.route('sma.nusinersen.lumbar_type_scope', 'skipped_not_applicable',
                           ['not_type_two_or_three'])
    elif observer is not None:
        observer.route('sma.nusinersen_specific_safety', 'skipped_not_applicable',
                       ['not_nusinersen'])
    return result('sma_safety_2025', reader, shared, sources)
