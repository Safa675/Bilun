# A0 uniqueness audit — `clause_coordinate`

Source: `/home/safa/Documents/Bilun/data/gazette/sut_clauses.parquet`

## Headline counts

| Metric | Value |
|--------|------:|
| Total parquet rows | 8295 |
| Null `clause_coordinate` | 16 |
| Section-only coordinates (no fıkra/bent) | 2352 |
| Encode-eligible (D4) | 3232 |

## Duplicate keys

| Key | Duplicate groups | Max group | Extra rows |
|-----|-----------------:|----------:|-----------:|
| clause_coordinate | 1486 | 242 | 5028 |
| coordinate + is_in_force | 1218 | 194 | 3979 |
| encode-eligible coordinate | 357 | 69 | 966 |
| encode-eligible coordinate + type | 308 | 68 | 861 |

## Encode-eligible collisions by clause_type

| clause_type | Dup groups | Max |
|-------------|-----------:|----:|
| bent | 183 | 39 |
| fikra | 53 | 3 |
| numbered_item | 72 | 68 |

## Top encode-eligible collisions

These are why dual-read must **fail loud** on ambiguous coordinates (Track A3) and why `C*` remains valid for collision-heavy cites (e.g. §4.2.14.C bent/numbered_item restarts).

| coordinate | type | n |
|------------|------|--:|
| `4.2.14.C.(1)` | numbered_item | 68 |
| `4.2.14.C.(2)` | numbered_item | 65 |
| `4.2.14.C.(3)` | numbered_item | 50 |
| `4.2.14.C.a` | bent | 39 |
| `4.2.14.C.b` | bent | 37 |
| `4.2.14.C.(4)` | numbered_item | 32 |
| `4.2.14.C.c` | bent | 26 |
| `4.2.14.C.(5)` | numbered_item | 16 |
| `4.2.14.C.ç` | bent | 16 |
| `3.3.26.(1)` | numbered_item | 12 |

## In-force clause_type census

| clause_type | n |
|------------|--:|
| fikra | 1520 |
| bent | 1166 |
| amendment | 559 |
| numbered_item | 546 |
| section_heading | 513 |
| prose | 400 |
| chapter | 6 |

## Policy implications (locked for Track A)

1. **Encode-eligible (D4):** `is_in_force` ∧ `clause_type ∈ {fikra,bent,numbered_item}` ∧ (`clause_number` OR `clause_letter` set).
2. **Null / chapter / part labels:** out of encode scope.
3. **Section-only coordinates:** not valid `gate_b_sources` cites.
4. **Coordinate resolve:** prefer in-force matches; if >1 row → `AmbiguousClauseCiteError` (use `C*` until richer cites exist).
5. **`C*` stays** as the unique row key through Track E; public YAML may use coordinates only when unique under the resolve policy.

