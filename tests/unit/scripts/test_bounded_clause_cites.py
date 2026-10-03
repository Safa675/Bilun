"""Explicit context anchors disambiguate byte-identical medicine clauses."""
import polars as pl
import pytest
from scripts.sut.prose.clause_identity import (
    resolve_gate_b_ref_to_clause_ids, UnknownClauseCiteError, AmbiguousClauseCiteError,
)

REF='4.2.14.C.b#769b2a20@between:4.2.14.C#c36e5ca4|4.2.14.C#024594a5'


def frame():
    return pl.DataFrame([
        {'clause_id':'C000001','paragraph_index':10,'clause_coordinate':'4.2.14.C','content_hash':'c36e5ca4','clause_type':'prose','is_in_force':True},
        {'clause_id':'C000002','paragraph_index':11,'clause_coordinate':'4.2.14.C.b','content_hash':'769b2a20','clause_type':'bent','is_in_force':True},
        {'clause_id':'C000003','paragraph_index':12,'clause_coordinate':'4.2.14.C','content_hash':'024594a5','clause_type':'prose','is_in_force':True},
        {'clause_id':'C000004','paragraph_index':13,'clause_coordinate':'4.2.14.C.b','content_hash':'769b2a20','clause_type':'bent','is_in_force':True},
    ]).with_columns(pl.lit(None).cast(pl.Int64).alias('clause_number'),
                    pl.when(pl.col('clause_type')=='bent').then(pl.lit('b')).otherwise(pl.lit('')).alias('clause_letter'))


def test_repeated_stop_text_is_resolved_only_inside_explicit_medicine_bounds():
    d=frame()
    # The old content-key API returns all equal-text rows. The bounded form
    # prevents this medicine's identical stop sentence linking another drug.
    assert resolve_gate_b_ref_to_clause_ids('4.2.14.C.b#769b2a20',d,encode_eligible_only=True)==['C000002','C000004']
    assert resolve_gate_b_ref_to_clause_ids(REF,d,encode_eligible_only=True)==['C000002']


@pytest.mark.parametrize('ref',[REF.replace('c36e5ca4','ffffffff'),REF.replace('4.2.14.C#c36e5ca4|4.2.14.C#024594a5','4.2.14.C#024594a5|4.2.14.C#c36e5ca4'),
    REF+'|third',REF.replace('4.2.14.C#c36e5ca4','C000001'),REF.replace('4.2.14.C.b#769b2a20','C000002')])
def test_malformed_missing_or_reversed_bounds_fail_closed(ref):
    with pytest.raises(UnknownClauseCiteError):
        resolve_gate_b_ref_to_clause_ids(ref,frame(),encode_eligible_only=True)


def test_duplicate_active_anchor_is_not_arbitrarily_selected():
    d=frame();d=pl.concat([d,d.filter(pl.col('clause_id')=='C000001')])
    with pytest.raises(UnknownClauseCiteError):resolve_gate_b_ref_to_clause_ids(REF,d)


def test_child_ambiguity_inside_window_still_fails():
    d=frame();duplicate=d.filter(pl.col('clause_id')=='C000002').with_columns(pl.lit('C000005').alias('clause_id'))
    with pytest.raises(AmbiguousClauseCiteError):resolve_gate_b_ref_to_clause_ids(REF,pl.concat([d,duplicate]))


def test_inactive_anchor_is_not_authority():
    d=frame().with_columns(pl.when(pl.col('clause_id')=='C000001').then(False).otherwise(pl.col('is_in_force')).alias('is_in_force'))
    with pytest.raises(UnknownClauseCiteError):resolve_gate_b_ref_to_clause_ids(REF,d)


def test_explicit_prose_anchor_is_content_pinned_not_a_blanket_relaxation():
    d=frame()
    assert resolve_gate_b_ref_to_clause_ids('prose:4.2.14.C#c36e5ca4',d,encode_eligible_only=True)==['C000001']
    with pytest.raises(UnknownClauseCiteError):resolve_gate_b_ref_to_clause_ids('prose:4.2.14.C#deadbeef',d)
    with pytest.raises(UnknownClauseCiteError):resolve_gate_b_ref_to_clause_ids('prose:C000001',d)
    with pytest.raises(UnknownClauseCiteError):resolve_gate_b_ref_to_clause_ids('prose:4.2.14.C.b#769b2a20',d)


@pytest.mark.parametrize('kind',['section_heading','chapter','amendment'])
def test_explicit_prose_cannot_cite_structural_or_amendment_rows(kind):
    from scripts.sut.prose.clause_identity import NonEncodeEligibleCiteError
    d=frame().with_columns(pl.when(pl.col('clause_id')=='C000001').then(pl.lit(kind)).otherwise(pl.col('clause_type')).alias('clause_type'))
    with pytest.raises(NonEncodeEligibleCiteError):resolve_gate_b_ref_to_clause_ids('prose:4.2.14.C#c36e5ca4',d)


def test_rule_catalog_api_uses_shared_extended_source_resolver(tmp_path,monkeypatch):
    import json
    from src.bilun.domain.sut import rules_catalog
    d=frame().with_columns(pl.lit('verified text').alias('in_force_text'),
                          (pl.col('clause_coordinate')+pl.lit('#')+pl.col('content_hash')).alias('clause_key'))
    (tmp_path/'test.json').write_text(json.dumps({'rule_set_id':'test','rules':[
        {'rule_id':'test.rule','sut_section':'4.2.14.C','gate_b_sources':[REF,'prose:4.2.14.C#c36e5ca4']},
        {'rule_id':'bad.rule','gate_b_sources':['prose:4.2.14.C#deadbeef']},
    ]}))
    monkeypatch.setattr(rules_catalog,'_PROSE_RULES_DIR',tmp_path)
    monkeypatch.setattr(rules_catalog,'_load_sut_clauses_frame',lambda:d)
    monkeypatch.setattr(rules_catalog,'_load_coverage',lambda:pl.DataFrame())
    good=rules_catalog.resolve_prose_rule_gate_b_sources('test','test.rule')['gate_b_sources']
    assert all(row['clause_key'] and row['text_snippet']=='verified text' for row in good)
    bad=rules_catalog.resolve_prose_rule_gate_b_sources('test','bad.rule')['gate_b_sources']
    assert bad[0]['clause_key'] is None and bad[0]['text_snippet'] is None


def test_source_catalog_retains_context_and_normalized_document_text_hashes():
    import hashlib,json
    from pathlib import Path
    source=json.loads((Path(__file__).resolve().parents[3]/'data/gazette/clinical_sources/enteral_ravulizumab_2026_10.json').read_text())
    assert source['docx_sha256']=='227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573'
    assert source['verified_through']=='2026-10-02'
    families={r['constraint_set']:r for r in source['families']}
    assert families['enteral_pediatric_reports_2026']['valid_from']=='2026-09-05'
    ravu=families['ravulizumab_nmosd_continuation_2026']
    assert ravu['valid_from']=='2026-07-07'
    for family in source['families']:
        for paragraph in family['source_paragraphs']:
            assert hashlib.sha256(paragraph['text'].encode()).hexdigest()==paragraph['sha256']
    stop=next(r for r in ravu['source_paragraphs'] if r['paragraph_index']==6123)
    assert stop['sha256']==ravu['duplicate_text_outside_scope']['sha256']
    assert all('@between:' in ref for ref in ravu['source_refs'])
    from src.bilun.domain.prose_rules._drug_indication.clinical_ravulizumab import SOURCE_REFS
    assert SOURCE_REFS == ravu['source_refs']
    clauses = pl.read_parquet(Path(__file__).resolve().parents[3]/'data/gazette/sut_clauses.parquet')
    assert resolve_gate_b_ref_to_clause_ids(SOURCE_REFS[-1], clauses) == ['C005809']
