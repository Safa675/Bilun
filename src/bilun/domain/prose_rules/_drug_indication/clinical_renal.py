"""Necessary renal thresholds from the verified SUT source snapshot.

The explicit clinical indication selects the branch; a drug name/ICD code alone
never establishes dialysis, surgical suitability, or nutritional eligibility.
Clear thresholds remain partial clinical review, not reimbursement approval.
"""
from typing import Any

from ...claims.clinical_evidence import RenalEvidence, parse_clinical_evidence
from .clinical_common import Predicate, Reader, all_of, any_of, result, scope_missing
from .runtime_observations import ClinicalObservationCollector, ObservedClinicalReader
from .matching import _drug_name_matches

PHOSPHATE_DRUGS = ('sevelamer', 'lantanyum karbonat', 'alüminyum klorür hidroksit')
CINACALCET_DRUGS = ('cinacalcet',)
NUTRITION_DRUGS = ('oral esansiyel aminoasit', 'oral esansiyel aminoasit preparatları',
                   'oral esansiyel aminoasit preperatları', 'keto analogları', 'keto analog')

PHOSPHATE_INITIAL = ['4.2.9.B.(1)#00052268', '4.2.9.B.a#2cbf02e7',
    '4.2.9.B.b#1438d4b8', '4.2.9.B.c#44af65a8', '4.2.9.B.ç#4843bec7']
PHOSPHATE_STOP = ['4.2.9.B.(3)#cbdee244']
PHOSPHATE_RESTART = ['4.2.9.B.(4)#e346bde0']
CINACALCET_INITIAL = ['4.2.9.Ç.(1)#d5f6d259']
CINACALCET_STOP = ['4.2.9.Ç.(2)#ab7653a8', '4.2.9.Ç.(3)#0a00af38']
CINACALCET_PRIMARY = ['4.2.9.Ç.(5)#deb19c81', '4.2.9.Ç.a#afe54fee', '4.2.9.Ç.b#568549ff']
NUTRITION_INITIAL = ['4.2.9.D.(1)#4dc7d730', '4.2.9.D.a#f13a1cdd', '4.2.9.D.b#914a33c4']
NUTRITION_STOP = ['4.2.9.D.a#7aa28a33', '4.2.9.D.b#a3749cdc']
NUTRITION_RESTART = ['4.2.9.D.c#6a824531']


def _unknown(field: str) -> Predicate:
    return Predicate(None, ('renal_evidence.' + field,))


def _phosphate(reader: Reader) -> tuple[Predicate, list[str]]:
    phase = reader.get('phase')
    reader.record_context('phase', 'indication')
    if reader.get('indication') != 'phosphate_binding':
        return _unknown('phosphate_binding_indication'), PHOSPHATE_INITIAL
    if phase in ('initiation', 'restart'):
        # The four criteria are alternatives, all following >=3 months of
        # another phosphate-lowering therapy, explicitly documented in the
        # report. Restart imports both requirements. Corrected and raw Ca×P differ.
        alternatives = any_of(
            reader.bound('phosphate.initial.raw_product', ['4.2.9.B.a#2cbf02e7']).number('calcium_phosphorus_product', '>=', 72),
            all_of(reader.bound('phosphate.initial.adynamic_bone', ['4.2.9.B.b#1438d4b8']).bool('adynamic_bone_disease'), reader.bound('phosphate.initial.low_pth', ['4.2.9.B.b#1438d4b8']).number('pth_pg_ml', '<', 100)),
            all_of(reader.bound('phosphate.initial.ktv_for_product', ['4.2.9.B.c#44af65a8']).number('kt_v', '>', 1.4),
                   reader.bound('phosphate.initial.corrected_product', ['4.2.9.B.c#44af65a8']).number('corrected_calcium_phosphorus_product', '>', 55)),
            all_of(reader.bound('phosphate.initial.ktv_for_pth', ['4.2.9.B.ç#4843bec7']).number('kt_v', '>', 1.4), reader.bound('phosphate.initial.high_pth', ['4.2.9.B.ç#4843bec7']).number('pth_pg_ml', '>=', 300)),
        )
        predicate = all_of(reader.bound('phosphate.initial.dialysis', ['4.2.9.B.(2)#8c267281']).bool('dialysis'),
            reader.bound('phosphate.initial.prior_months', ['4.2.9.B.(1)#00052268']).number('other_phosphate_therapy_months', '>=', 3),
            reader.bound('phosphate.initial.prior_therapy_report', ['4.2.9.B.(1)#00052268']).bool('prior_phosphate_therapy_documented_in_report'), alternatives)
        sources = PHOSPHATE_INITIAL + ['4.2.9.B.(2)#8c267281']
        if phase == 'restart':
            predicate = all_of(predicate, reader.bound('phosphate.restart.phosphorus', ['4.2.9.B.(4)#e346bde0']).number('phosphorus_mg_dl', '>', 4))
            sources += PHOSPHATE_RESTART
        return predicate, sources
    if phase == 'continuation':
        return all_of(reader.bound('phosphate.continuation.dialysis', ['4.2.9.B.(2)#8c267281']).bool('dialysis'), reader.bound('phosphate.continuation.phosphorus', ['4.2.9.B.(3)#cbdee244']).number('phosphorus_mg_dl', '>=', 3.5)), PHOSPHATE_STOP
    return _unknown('phase'), PHOSPHATE_INITIAL + PHOSPHATE_STOP + PHOSPHATE_RESTART


def _cinacalcet(reader: Reader) -> tuple[Predicate, list[str]]:
    indication, phase = reader.get('indication'), reader.get('phase')
    reader.record_context('indication', 'phase')
    if indication == 'dialysis_shpt':
        if phase == 'initiation':
            return all_of(reader.bound('cinacalcet.initial.dialysis', ['4.2.9.Ç.(1)#d5f6d259']).bool('dialysis'), reader.bound('cinacalcet.initial.calcium', ['4.2.9.Ç.(1)#d5f6d259']).number('corrected_calcium_mg_dl', '>=', 8.5),
                          reader.bound('cinacalcet.initial.pth', ['4.2.9.Ç.(1)#d5f6d259']).number('pth_pg_ml', '>=', 600)), CINACALCET_INITIAL
        if phase == 'continuation':
            # Stop at corrected calcium <=8.4 OR PTH <300, in dialysis patients.
            return all_of(reader.bound('cinacalcet.continuation.dialysis', ['4.2.9.Ç.(2)#ab7653a8']).bool('dialysis'), reader.bound('cinacalcet.continuation.calcium', ['4.2.9.Ç.(2)#ab7653a8']).number('corrected_calcium_mg_dl', '>', 8.4),
                          reader.bound('cinacalcet.continuation.pth', ['4.2.9.Ç.(3)#0a00af38']).number('pth_pg_ml', '>=', 300)), CINACALCET_STOP
        # The source does not specify a separate restart branch. Do not silently
        # use initiation or continuation thresholds for an unreviewed restart.
        return _unknown('source_supported_treatment_phase'), CINACALCET_INITIAL + CINACALCET_STOP
    if indication == 'primary_hpt':
        alternatives = any_of(reader.bound('cinacalcet.primary.asa_iv', ['4.2.9.Ç.a#afe54fee']).bool('asa_iv'), all_of(
            reader.bound('cinacalcet.primary.recurrence', ['4.2.9.Ç.b#568549ff']).bool('postsurgical_recurrence'), reader.bound('cinacalcet.primary.bisphosphonate_failure', ['4.2.9.Ç.b#568549ff']).bool('bisphosphonate_failed'),
            reader.bound('cinacalcet.primary.calcium', ['4.2.9.Ç.b#568549ff']).number('corrected_calcium_mg_dl', '>=', 10.5)))
        return all_of(reader.bound('cinacalcet.primary.surgery_indicated', ['4.2.9.Ç.(5)#deb19c81']).bool('parathyroidectomy_indicated'),
                      reader.bound('cinacalcet.primary.surgery_contraindicated', ['4.2.9.Ç.(5)#deb19c81']).bool('parathyroidectomy_unsuitable_or_contraindicated'), alternatives), CINACALCET_PRIMARY
    # E.g. parathyroid carcinoma is another legitimate drug indication. Never
    # reject it based on dialysis/primary-hyperparathyroidism restrictions.
    return _unknown('supported_renal_indication'), CINACALCET_INITIAL + CINACALCET_PRIMARY


def _nutrition(reader: Reader) -> tuple[Predicate, list[str]]:
    reader.record_context('indication')
    if reader.get('indication') != 'renal_nutrition':
        return _unknown('renal_nutrition_indication'), NUTRITION_INITIAL
    phase = reader.get('phase')
    reader.record_context('phase')
    if phase in ('initiation', 'restart'):
        stage = reader.get('ckd_stage')
        if stage is not None and stage not in (1, 2, 3, 4, 5):
            reader.block_invalid_input('invalid_ckd_stage', 'ckd_stage')
            return _unknown('valid_ckd_stage'), NUTRITION_INITIAL
        population = any_of(reader.bound('nutrition.initial.stage_five', ['4.2.9.D.(1)#4dc7d730']).number('ckd_stage', '==', 5),
            all_of(reader.bound('nutrition.initial.stage_four', ['4.2.9.D.(1)#4dc7d730']).number('ckd_stage', '==', 4), reader.bound('nutrition.initial.gfr', ['4.2.9.D.(1)#4dc7d730']).number('gfr_ml_min', '<', 30)))
        weight_loss = reader.get('weight_loss_last_3_months_percent')
        bmi = reader.get('bmi')
        # A zero BMI or loss of all/more than all body weight is invalid
        # evidence, not a way to satisfy a clinical threshold.
        loss_check = (reader.bound('nutrition.initial.weight_loss', ['4.2.9.D.a#f13a1cdd']).unknown(
                      'weight_loss_last_3_months_percent', _unknown('weight_loss_last_3_months_percent'))
                      if weight_loss is not None and weight_loss >= 100
                      else reader.bound('nutrition.initial.weight_loss', ['4.2.9.D.a#f13a1cdd']).number('weight_loss_last_3_months_percent', '>=', 10))
        bmi_check = (reader.bound('nutrition.initial.bmi', ['4.2.9.D.b#914a33c4']).unknown(
                     'bmi', _unknown('bmi')) if bmi is not None and bmi <= 0
                     else reader.bound('nutrition.initial.bmi', ['4.2.9.D.b#914a33c4']).number('bmi', '<', 19))
        nutritional = any_of(loss_check, bmi_check)
        predicate = all_of(reader.bound('nutrition.initial.albumin', ['4.2.9.D.(1)#4dc7d730']).number('albumin_g_dl', '<', 3.5), population, nutritional)
        return predicate, NUTRITION_INITIAL + (NUTRITION_RESTART if phase == 'restart' else [])
    if phase == 'continuation':
        months = reader.get('therapy_months')
        reader.record_context('therapy_months')
        if months is None:
            return _unknown('therapy_months'), NUTRITION_STOP
        checks = []
        if months >= 3:
            checks.append(reader.bound('nutrition.continuation.current_albumin', ['4.2.9.D.b#a3749cdc']).number('albumin_g_dl', '<=', 4))
        if months >= 6:
            baseline = reader.get('baseline_albumin_g_dl')
            if baseline is None or baseline <= 0:
                checks.append(reader.bound('nutrition.continuation.six_month_response',
                    ['4.2.9.D.a#7aa28a33']).unknown('baseline_albumin_g_dl',
                                                 _unknown('positive_baseline_albumin_g_dl')))
            else:
                reader.record_context('baseline_albumin_g_dl')
                # A later current value cannot replace the response measured
                # at the first six-month checkpoint.
                response_field = ('albumin_g_dl' if months == 6
                                  else 'six_month_albumin_g_dl')
                checks.append(reader.bound('nutrition.continuation.six_month_response', ['4.2.9.D.a#7aa28a33']).number(response_field, '>=', baseline * 1.25))
        if not checks:
            # Before the source's 3/6-month checkpoints no numerical continuation
            # predicate has run; do not report an empty conjunction as clear.
            return _unknown('source_continuation_checkpoint'), NUTRITION_STOP
        return all_of(*checks), NUTRITION_STOP
    return _unknown('phase'), NUTRITION_INITIAL + NUTRITION_STOP + NUTRITION_RESTART


def evaluate_renal(line: Any, *, observer: ClinicalObservationCollector | None = None) -> dict[str, Any]:
    """Evaluate one recognized medicine family; multiple families need review."""
    evidence = parse_clinical_evidence(getattr(line, 'renal_evidence', None), RenalEvidence)
    reader = ObservedClinicalReader(evidence, 'renal_evidence', observer)
    if observer is not None:
        observer.context('drug_name')
    families = [name for name, drugs in (
        ('phosphate', PHOSPHATE_DRUGS), ('cinacalcet', CINACALCET_DRUGS), ('nutrition', NUTRITION_DRUGS),
    ) if _drug_name_matches(line.drug_name, list(drugs))]
    sources = (PHOSPHATE_INITIAL + PHOSPHATE_STOP + PHOSPHATE_RESTART if families == ['phosphate']
               else CINACALCET_INITIAL + CINACALCET_STOP + CINACALCET_PRIMARY if families == ['cinacalcet']
               else NUTRITION_INITIAL + NUTRITION_STOP + NUTRITION_RESTART if families == ['nutrition'] else [])
    date_missing = scope_missing(evidence, 'renal_evidence', line.drug_claim_date,
                                 'renal', reader=reader)
    if observer is not None:
        if 'drug_claim_date' not in date_missing:
            observer.context('drug_claim_date')
        if 'verified_source_for_service_date' not in date_missing and 'drug_claim_date' not in date_missing:
            for field in ('applies_on', 'assessment_date'):
                if 'renal_evidence.' + field not in date_missing:
                    observer.context('renal_evidence.' + field)
    if date_missing:
        if observer is not None:
            blocked_source = 'verified_source_for_service_date' in date_missing
            observer.route('renal.source_date', 'blocked_source' if blocked_source else 'blocked_inputs',
                ['unsupported_source_date' if blocked_source else 'missing_or_invalid_scope_fact'],
                [] if blocked_source else date_missing)
        return result('renal_source_constraints', reader, Predicate(None), sources,
                      date_missing=date_missing)
    if len(families) != 1:
        if observer is not None:
            observer.route('renal.medicine_family', 'blocked_source', ['unsupported_or_ambiguous_medicine_family'])
        return result('renal_source_constraints', reader, _unknown('single_supported_medicine_family'), sources)
    evaluator = {'phosphate': _phosphate, 'cinacalcet': _cinacalcet, 'nutrition': _nutrition}[families[0]]
    predicate, sources = evaluator(reader)
    if observer is not None and not observer.receipts:
        # No comparison was reached. Keep unsupported source/phase branches
        # separate from absent validated input facts.
        missing_fields = [f for f in ('indication', 'phase', 'therapy_months', 'ckd_stage')
                          if reader.get(f) is None and any(f in reason for reason in predicate.missing)]
        if missing_fields:
            observer.route('renal.branch', 'blocked_inputs', ['missing_branch_input'],
                           ['renal_evidence.' + f for f in missing_fields])
        else:
            observer.route('renal.branch', 'blocked_source', ['unsupported_clinical_branch'])
    return result('renal_source_constraints', reader, predicate, sources)
