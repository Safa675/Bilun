"""Source admission is a reviewed evidence window, never a new enactment date."""
from copy import deepcopy
from datetime import date, datetime
from types import SimpleNamespace
import json
import shutil

import polars as pl
import pytest
from pydantic import ValidationError

from src.bilun.domain.prose_rules._drug_indication import source_authority as authority
from src.bilun.domain.prose_rules._drug_indication.clinical_common import Reader, scope_missing
from src.bilun.domain.sut.source_authority_schema import bounded_source_authority


FAMILIES = ('sma', 'antifungal_micafungin', 'antifungal_other', 'renal', 'enteral',
            'ravulizumab', 'followup', 'indication_sc_ig', 'indication_hbv',
            'indication_hcv', 'indication_bone', 'mecasermin')


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('day,admitted', [('2026-10-02', True), ('2026-10-03', True),
                                        ('2026-10-04', False), ('2030-01-01', False)])
def test_all_capped_families_have_explicit_current_bounds(family, day, admitted):
    result = authority.resolve_source_authority(family, day)
    assert (result.status == 'admitted') is admitted
    assert result.clinical_eligibility_complete is False
    assert result.scope == 'named_clinical_report_checks_only'
    assert result.official_review_checked_at == '2026-10-03T07:04:00Z'
    if day == '2026-10-03':
        assert result.admission_basis == 'reviewed_continuity'
        assert result.source_observed_on == '2026-10-02'
        assert result.admitted_from == result.admitted_through == day
    if not admitted:
        assert result.reason == 'uncovered_service_date'
        assert 'SGK' in result.next_action and 'Gazette' in result.next_action


@pytest.mark.parametrize('family,lower', [('sma', '2025-05-06'), ('antifungal_micafungin', '2018-04-01'),
    ('enteral', '2026-09-05'), ('ravulizumab', '2026-07-07'),
    ('indication_sc_ig', '2024-11-09'), ('indication_hbv', '2024-11-09')])
def test_established_lower_bound_is_preserved(family, lower):
    start = date.fromisoformat(lower)
    assert authority.resolve_source_authority(family, start).status == 'admitted'
    assert authority.resolve_source_authority(family, date.fromordinal(start.toordinal()-1)).status == 'review_required'
    assert authority.resolve_source_authority(family, date.fromordinal(start.toordinal()+1)).status == 'admitted'


@pytest.mark.parametrize('family', ['antifungal_other', 'renal', 'followup', 'indication_hcv', 'indication_bone', 'mecasermin'])
def test_unknown_history_stays_unknown(family):
    result = authority.resolve_source_authority(family, '2026-10-01')
    assert result.status == 'review_required' and result.legal_effective_from is None
    assert authority.resolve_source_authority(family, '2026-10-03').legal_effective_from is None


def test_mecasermin_points_are_not_interpolated():
    august = authority.resolve_source_authority('mecasermin', '2026-08-29')
    assert august.status == 'admitted' and august.source_observed_on == '2026-08-29'
    assert august.source_docx_sha256 == 'e6697a42cb24e20335c0a59ef9f9b7554d95a2db9a0280a90617564df9538821'
    for day in ('2026-08-28', '2026-08-30', '2026-09-15', '2026-10-01'):
        assert authority.resolve_source_authority('mecasermin', day).status == 'review_required'


@pytest.mark.parametrize('value', [None, '', 'today', True, datetime(2026,10,3), '2026-10-03T00:00:00Z', '2026-02-30'])
def test_no_missing_date_or_timestamp_is_replaced_by_today(value):
    result = authority.resolve_source_authority('renal', value)
    assert result.reason == 'missing_service_date' and result.service_date is None


def test_source_gate_keeps_fact_dates_independent():
    service = date(2026,10,3)
    evidence = SimpleNamespace(applies_on=date(2026,10,2), assessment_date=date(2026,10,4))
    reader = Reader(evidence,'renal_evidence')
    assert scope_missing(evidence,'renal_evidence',service,'renal',reader=reader) == [
        'renal_evidence.applies_on', 'renal_evidence.assessment_date']
    assert reader.source_authority['status'] == 'admitted'


@pytest.mark.parametrize('mutation', ['extra', 'overlap', 'invalid_date', 'future_review', 'unknown_history', 'missing_review'])
def test_strict_catalog_rejects_invented_authority(mutation):
    raw = json.loads(authority._CATALOG.read_text())
    row = next(x for x in raw['versions'] if x['family_id']=='renal')
    if mutation == 'extra': row['date_today_authority'] = True
    elif mutation == 'overlap': row['windows'].append(deepcopy(row['windows'][-1]))
    elif mutation == 'invalid_date': row['windows'][0]['start'] = '2026-02-30'
    elif mutation == 'future_review': raw['official_reviews'][0]['checked_through'] = '2026-10-04'
    elif mutation == 'unknown_history':
        row['windows'][0].update(basis='established_history',observed_source_sha256=None)
    else: row['windows'][-1]['review_id'] = 'absent'
    with pytest.raises(ValidationError): authority.AuthorityCatalog.model_validate(raw)


def test_missing_catalog_and_corrupt_proof_are_source_review(tmp_path,monkeypatch):
    authority._parse_catalog.cache_clear()
    with monkeypatch.context() as patch:
        patch.setattr(authority,'_CATALOG',tmp_path/'missing.json')
        assert authority.resolve_source_authority('renal','2026-10-03').reason == 'source_authority_unavailable'
    raw=json.loads(authority._CATALOG.read_text())
    raw['official_reviews'][0]['evidence'][0]['sha256']='0'*64
    bad=tmp_path/'bad.json';bad.write_text(json.dumps(raw))
    with monkeypatch.context() as patch:
        patch.setattr(authority,'_CATALOG',bad)
        assert authority.resolve_source_authority('renal','2026-10-03').reason == 'source_authority_unavailable'
    authority._parse_catalog.cache_clear()


def test_changed_live_source_text_fails_closed(monkeypatch):
    from src.bilun.domain.sut import rules_catalog
    frame=rules_catalog._load_sut_clauses_frame()
    changed=frame.with_columns(pl.when(pl.col('clause_key')=='4.2.49.(5)#597ea9c2')
        .then(pl.lit('changed clinical source')).otherwise(pl.col('in_force_text')).alias('in_force_text'))
    monkeypatch.setattr(authority,'_parse_corpus',lambda payload:changed)
    result=authority.resolve_source_authority('sma','2026-10-03')
    assert result.status=='review_required' and result.reason=='source_content_changed'


def test_corpus_parser_cache_is_content_keyed_not_process_snapshot():
    import io
    first=pl.DataFrame({'parent_section_id':['old-parent'],'in_force_text':['same-child']})
    second=pl.DataFrame({'parent_section_id':['new-parent'],'in_force_text':['same-child']})
    before,after=io.BytesIO(),io.BytesIO()
    first.write_parquet(before);second.write_parquet(after)
    authority._parse_corpus.cache_clear()
    assert authority._parse_corpus(before.getvalue())['parent_section_id'][0]=='old-parent'
    assert authority._parse_corpus(after.getvalue())['parent_section_id'][0]=='new-parent'


def test_known_successor_blocks_prior_version_even_with_a_wide_review(monkeypatch):
    raw=authority.load_source_authority().model_dump()
    row=next(x for x in raw['versions'] if x['family_id']=='renal')
    row['known_successor_from']='2026-10-03'
    catalog=authority.AuthorityCatalog.model_validate(raw)
    monkeypatch.setattr(authority,'load_source_authority',lambda:catalog)
    assert authority.resolve_source_authority('renal','2026-10-02').status=='admitted'
    assert authority.resolve_source_authority('renal','2026-10-03').reason=='known_successor'


def test_later_positive_review_can_extend_without_evaluator_or_legal_date_edit(monkeypatch):
    raw=authority.load_source_authority().model_dump()
    raw['official_reviews'][0].update(checked_at='2026-10-04T07:04:00Z',checked_through='2026-10-04')
    row=next(x for x in raw['versions'] if x['family_id']=='renal')
    row['windows'][-1]['through']='2026-10-04'
    # Synthetic in-memory review tests the data contract, not an actual Oct4 admission.
    catalog=authority.AuthorityCatalog.model_validate(raw)
    monkeypatch.setattr(authority,'load_source_authority',lambda:catalog)
    result=authority.resolve_source_authority('renal','2026-10-04')
    assert result.status=='admitted' and result.legal_effective_from is None


def test_public_evidence_rejects_inconsistent_or_invalid_dates():
    raw=authority.resolve_source_authority('renal','2026-10-03').model_dump()
    for extra in ({'status':'review_required'}, {'service_date':'2026-02-30'},
                  {'admitted_through':'2026-10-02'}, {'raw_patient_record':'secret'},
                  {'legal_effective_from':'2027-01-01'}, {'admitted_through':'2026-10-04'}):
        assert bounded_source_authority({**raw,**extra}) is None


@pytest.mark.parametrize('mutation',['lower_history','invented_point','date_only_refresh',
                                    'swapped_family','backdated_observation','invented_legal_start'])
def test_catalog_dates_cannot_outgrow_pinned_proof(tmp_path,monkeypatch,mutation):
    raw=json.loads(authority._CATALOG.read_text())
    if mutation=='lower_history':
        raw['versions'][0]['windows'][0]['start']='2025-05-05'
    elif mutation=='invented_point':
        row=next(x for x in raw['versions'] if x['family_id']=='renal')
        row['windows'].insert(0,{'start':'2026-10-01','through':'2026-10-01',
            'basis':'observed_snapshot','observed_source_sha256':row['source_docx_sha256']})
    elif mutation=='date_only_refresh':
        raw['official_reviews'][0].update(checked_at='2026-10-04T07:04:00Z',checked_through='2026-10-04')
        for row in raw['versions']:row['windows'][-1]['through']='2026-10-04'
    else:
        row=next(x for x in raw['versions'] if x['family_id']=='renal')
        if mutation=='swapped_family':
            row['evidence']=next(x['evidence'] for x in raw['versions'] if x['family_id']=='followup')
        elif mutation=='backdated_observation':
            row['source_observed_on']='2026-10-01'
            row['windows'][0].update(start='2026-10-01',through='2026-10-01')
        else:
            row['legal_effective_from']='2026-10-01'
            row['windows'][0].update(start='2026-10-01',basis='established_history',observed_source_sha256=None)
    path=tmp_path/'unsupported.json';path.write_text(json.dumps(raw))
    monkeypatch.setattr(authority,'_CATALOG',path)
    result=authority.resolve_source_authority('renal','2026-10-03')
    assert result.status=='review_required' and result.reason=='source_authority_unavailable'


@pytest.mark.parametrize('mutation',['missing_corpus','changed_context','missing_proof'])
def test_warmed_caches_cannot_hide_missing_or_changed_deployed_assets(tmp_path,monkeypatch,mutation):
    from scripts.sut.verify_clinical_source_authority import verify
    report=verify()
    original=authority._ROOT
    for relative in report['assets']:
        target=tmp_path/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(original/relative,target)
    monkeypatch.setattr(authority,'_ROOT',tmp_path)
    monkeypatch.setattr(authority,'_CATALOG',tmp_path/'data/gazette/source_authority/clinical_versions.json')
    assert authority.resolve_source_authority('renal','2026-10-03').status=='admitted'
    corpus=tmp_path/'data/gazette/sut_clauses.parquet'
    if mutation=='missing_corpus':corpus.unlink()
    elif mutation=='changed_context':
        frame=pl.read_parquet(corpus)
        # Identical clinical child/coordinate, altered parent context only.
        frame.with_columns(pl.when(pl.col('section_id').str.starts_with('4.2.9'))
            .then(pl.lit('wrong_same_section_parent')).otherwise(pl.col('parent_section_id'))
            .alias('parent_section_id')).write_parquet(corpus)
    else:
        (tmp_path/'data/gazette/source_authority/rg-20261003-3-regulation-observer-text.txt').unlink()
    result=authority.resolve_source_authority('renal','2026-10-03')
    assert result.status=='review_required'
    assert 'SGK' in result.next_action


@pytest.mark.parametrize('family,drug', [('sma','nusinersen'),('antifungal','anidulafungin'),
    ('renal','cinacalcet'),('enteral','enteral'),('ravulizumab','ravulizumab'),
    ('followup','dupilumab'),('indications','scig'),('indications','entekavir'),
    ('indications','ribavirin'),('indications','denosumab')])
def test_actual_family_gates_admit_today_and_preserve_stale_source_observations(family,drug):
    from src.bilun.domain.claims import clinical_evidence as evidence_types
    from src.bilun.domain.prose_rules._drug_indication import (
        clinical_sma,clinical_antifungal,clinical_renal,clinical_enteral,
        clinical_ravulizumab,clinical_followup,clinical_indications,
    )
    from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
    specs={
        'sma':(evidence_types.SmaEvidence,clinical_sma.evaluate_sma_safety,'sma_evidence',{}),
        'antifungal':(evidence_types.AntifungalEvidence,clinical_antifungal.evaluate_antifungal,'antifungal_evidence',{}),
        'renal':(evidence_types.RenalEvidence,clinical_renal.evaluate_renal,'renal_evidence',{}),
        'enteral':(evidence_types.EnteralEvidence,clinical_enteral.evaluate_enteral_reports,'enteral_evidence',{'pediatric':True,'malnutrition_path':'malnutrition'}),
        'ravulizumab':(evidence_types.RavulizumabEvidence,clinical_ravulizumab.evaluate_ravulizumab_continuation,'ravulizumab_evidence',{'indication':'nmosd','adult':True}),
        'followup':(evidence_types.FollowupEvidence,clinical_followup.evaluate_followup,'followup_evidence',{}),
        'indications':(evidence_types.IndicationEvidence,clinical_indications.evaluate_indications,'indication_evidence',{}),
    }
    model,evaluator,field,facts=specs[family]
    outcomes=[]
    for day in (date(2026,10,2),date(2026,10,3),date(2026,10,4)):
        line=SimpleNamespace(drug_name=drug,drug_claim_date=day,drug_report_duration_months=6,
            claim_id='SYNTHETIC-DATE-AUTHORITY',drug_claim_line_id='SYNTHETIC-LINE',
            **{field:model(applies_on=day,assessment_date=day,**facts)})
        observer=ClinicalObservationCollector(line,family,'source-authority-test')
        result=(evaluator(line,observer=observer) if family in ('sma','antifungal','renal') else evaluator(line))
        assert result['clinical_eligibility_complete'] is False
        assert result['source_authority']['status']==('review_required' if day.day==4 else 'admitted')
        if day.day==4:
            assert result['criterion_status']=='not_evaluated' and result['checks']==[]
            assert result['missing_inputs']==['verified_source_for_service_date']
            if family in ('sma','antifungal','renal'):
                assert all(row['kind']=='route' and row['status']=='blocked_source' for row in observer.receipts)
        else:
            outcomes.append({key:value for key,value in result.items() if key!='source_authority'})
    assert outcomes[0]==outcomes[1]
