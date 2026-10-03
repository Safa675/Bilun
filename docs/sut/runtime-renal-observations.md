# Observed renal execution coverage

This follow-on adds request-local measurements to the reviewed renal necessary-constraint evaluator. It preserves clinical results and the static coverage catalog. Static catalog runtime counts remain null. No patient values are logged or copied into execution receipts.

## Scope and output

For a matched renal family, an ephemeral collector emits stable predicate/source receipts directly at each reached comparison. `all_of`/`any_of` arguments are eager, so all reached comparisons are recorded, including false alternatives to a successful OR. An atomic false predicate is not a billing violation. Source-date, invalid-input and unsupported-branch blocks are recorded separately and do not invent downstream predicate attempts.

The per-line family result carries `clinical_restrictions[i].runtime_coverage` through canonical billing, findings/evaluations/legacy projection, public DTOs, strict V2 advisories and cache JSON. Only the renal family is instrumented in this patch. GH/SMA/antifungal and other families omit the runtime object until their actual hooks are added.

The counters have different units:

- Input facts: distinct validated facts actually read on the observed path, including validated date/route context. Supplied but unused facts are not included; this is observed-path availability, not a count of all possible chart fields.
- Predicates: actual semantic comparison attempts, partitioned into known true, known false and missing-input results. Repeated use of one fact can support different predicates without increasing the unique fact count.
- Source clauses touched: unique source IDs resolved from those actual receipts. Active normative rows and exact identity are required; unverified/ambiguous/structural references make source metrics unavailable while retaining measured predicate counts.
- Fully evaluated source clauses: null here. A separately reviewed complete-clause mapping is required; atom observations or a family source-list cannot establish complete legal-clause execution.

An explicit empty observation set is measured zero. Absent instrumentation is unavailable, never zero. Conflicting receipt identities and foreign/orphan contexts fail closed. Anonymous ad-hoc claims are accepted only when their empty claim ID is explicitly registered in the current request's allowed contexts and matches a private execution scope. Two different request-local collectors cannot be mixed, even with identical empty claim/line IDs. The scope identifier is never exposed or included in the reproducible receipt digest.

## Source status nuance

The extractor's `is_superseded_marker` means an inline “Mülga” token exists, including deleted fragments inside otherwise active clauses. It is not a whole-clause repeal flag. C004224 is a real regression example: active normative text, containing an inline deleted phrase. Actual `is_in_force`, normative kind and non-heading/non-amendment status remain required.

## Integration and verification

Base is the exact staged A/GH/D integration tree. In particular, the approved A endpoint uses `model_dump(mode="json")`; default dumping typed clinical dates would break V2 request-provenance serialization. The actual anonymous and named request tests exercise the real route, not only raw dictionaries.

A complete phosphate example reads 13 validated context/clinical facts, executes 9 atomic comparisons and touches 6 verified source clauses. Its criterion is clear through an OR branch, despite 6 alternative comparisons being false; overall clinical eligibility remains incomplete. Missing PTH produces two unknown predicates but one missing input fact. Unknown or unsupported service dates produce zero clinical comparison attempts with an explicit blocked-route observation.

The strict public runtime schema and bounded serializer reject inconsistent count partitions, malformed source identities and unapproved fields. The unavailable-state DTO applies the same bounded identifier/reason validation and rejects every non-null counter, source flag/list or receipt digest. Malformed unavailable summaries cannot retain measurement claims. Both availability states reject duplicate identity arrays and overlong reasons rather than validating a sanitized copy and returning raw data. Raw patient measurements and complete receipt objects are not public. Public/cache tests preserve verified source IDs, counts and explicit null full-clause metrics; private fields are stripped.

Local Python 3.13 final focused verification: 264 tests pass, including 70 original renal semantic tests, receipt invariants, 33 new hostile available/unavailable-state and round-trip regressions, real named/anonymous V2 requests and public/cache/API tests. Ruff passes. Before the DTO review correction, the broader domain run passed 3,453 tests with 24 skipped; all 49 failures reproduced on exact D61 with identical errors after normalizing checkout paths and object memory addresses.

Full-suite validation is incomplete. An initial run exhausted the shared 4.9 GB `/tmp` tmpfs; a subsequent workspace-basetemp run reached 91% before the process was killed with only 119 MB free. Neither counts as a pass. Disposable output from the terminated runs was removed, while frozen packets and logs were preserved. The first whole-suite failure (missing section coverage parquet) reproduces on exact D61. Subsequent local gates use bounded test sets and explicit sibling workspace TMPDIR/basetemp. Complete hosted CI is still required.

No whole-SUT percentage, complete eligibility, monetary conclusion, persistent patient logging, merge or deployment is introduced.
