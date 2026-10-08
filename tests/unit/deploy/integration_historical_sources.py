"""Exact historical public source bodies, never deployment admission."""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
from pathlib import Path

_PINNED_ARCHIVES = {'clinical_baseline': {'source_commit': '3f5540cf199cb464b1fca1d7d7d6ff024d5edc3b',
                       'source_tree': '7acefd250cf56d06ff92ddd2e9933d28695f615a',
                       'sources': {'src/bilun/api/routes/billing.py': {'blob_sha1': '6cd6f86c92f1deb533692090def668fb00e2bb1d',
                                                                       'mode': '100644',
                                                                       'sha256': '8b706e352dc903dab57c9cafefb8f51aaa523d19f65f960e98ad8c10b9984ffb',
                                                                       'size_bytes': 13372,
                                                                       'type': 'blob'},
                                   'src/bilun/api/schemas.py': {'blob_sha1': 'c7d2e3d5bb738c83de23f83f7541d0acc20014f7',
                                                                'mode': '100644',
                                                                'sha256': 'e384189d1b176cec302e33560a356e6032dfbff720b67de4d51177b19c1f6b20',
                                                                'size_bytes': 38310,
                                                                'type': 'blob'},
                                   'src/bilun/domain/billing/drug_indication_findings.py': {'blob_sha1': 'f7846924f31b3edf6e92a7e77c0f758d01c5688d',
                                                                                            'mode': '100644',
                                                                                            'sha256': '53f0aea62c9b4cb46f8720ed286a142dcc3534f9268ed15f750a966bcf362dc0',
                                                                                            'size_bytes': 26637,
                                                                                            'type': 'blob'}}},
 'clinical_candidate': {'source_commit': '3e0e0c6d88fdcd4817e0a7a84b3361184d78b1ea',
                        'source_tree': '6f102905fc1e150de89eefdac91fddbfdff10d10',
                        'sources': {'src/bilun/api/routes/billing.py': {'blob_sha1': '6cd6f86c92f1deb533692090def668fb00e2bb1d',
                                                                        'mode': '100644',
                                                                        'sha256': '8b706e352dc903dab57c9cafefb8f51aaa523d19f65f960e98ad8c10b9984ffb',
                                                                        'size_bytes': 13372,
                                                                        'type': 'blob'},
                                    'src/bilun/api/schemas.py': {'blob_sha1': '793ea286c450144de98c37a2ae7834287532dbb7',
                                                                 'mode': '100644',
                                                                 'sha256': '3360adab448a9c457f63d21817beb5b648fbfa0ec41d44c868326d6a48b40015',
                                                                 'size_bytes': 40731,
                                                                 'type': 'blob'},
                                    'src/bilun/domain/billing/drug_indication_findings.py': {'blob_sha1': '816dc972d8f2b8f317dc2c228baaef91e9bf5c61',
                                                                                             'mode': '100644',
                                                                                             'sha256': 'b8f81882bd78a21e98fd9b948d145987996a5a61a6a5b3fb5cc511de7391d1e4',
                                                                                             'size_bytes': 30974,
                                                                                             'type': 'blob'}}},
 'shared_interpreter': {'source_commit': '5c89ed53f2545c2d27072d630a46249b31091736',
                        'source_tree': '83b7b09b210dadcc5b4a7e81a60808b071382885',
                        'sources': {'docs/operations/single-vps-wavea-release.md': {'blob_sha1': '1b9f1021899936cef6b613348494bb4b5f0a2c8e',
                                                                                    'mode': '100644',
                                                                                    'sha256': 'd5d782fb546f661b37aad4e475c22a4850bec16620129eab8ea8afa44a4fc783',
                                                                                    'size_bytes': 21001,
                                                                                    'type': 'blob'},
                                    'scripts/deploy/capture_release_preflight.py': {'blob_sha1': 'db250469b7df4a44f14bd95d47ef568c2c8355a9',
                                                                                    'mode': '100644',
                                                                                    'sha256': '1598d6cf10d6caab76f08320622984105f962d21509f6b0a949ac8ee89eba224',
                                                                                    'size_bytes': 35400,
                                                                                    'type': 'blob'},
                                    'scripts/deploy/issue_wavea_activation.py': {'blob_sha1': '8212e476b2a4c7c0092fa711b510a13ef2947552',
                                                                                 'mode': '100644',
                                                                                 'sha256': '47b18712a35b9cb7d1c9bc61c2c51e735fcbd46b712bd11e9f3cc63388c64841',
                                                                                 'size_bytes': 36661,
                                                                                 'type': 'blob'},
                                    'scripts/deploy/rehearse_wavea_same_port.py': {'blob_sha1': '4987802783fc700760190d44baabd2b186d20295',
                                                                                   'mode': '100644',
                                                                                   'sha256': '2f884bb4304fdd20842ae501033197d53b6dc1f85d1308c65a0235b928fa9e56',
                                                                                   'size_bytes': 58582,
                                                                                   'type': 'blob'},
                                    'scripts/deploy/verify_final_source_refresh_transition.py': {'blob_sha1': 'db36d75dac28abfaa21fe1f067a7b6fa918dc099',
                                                                                                 'mode': '100644',
                                                                                                 'sha256': '3b593fb88b7db167c3f6245f5ff36c05a8b497e10c5877a9c1f6b24accff4349',
                                                                                                 'size_bytes': 115244,
                                                                                                 'type': 'blob'},
                                    'tests/unit/deploy/fixtures/final_source_refresh_mainc44_tooling.json': {'blob_sha1': '12bba3259806cca50053686056f5998e4ade5478',
                                                                                                             'mode': '100644',
                                                                                                             'sha256': 'af07f77275ce6c6665b0a742820b50ed4779ae58a572b96359bf86c9b15af426',
                                                                                                             'size_bytes': 105854,
                                                                                                             'type': 'blob'},
                                    'tests/unit/deploy/fixtures/final_source_refresh_mainf28_tooling.json': {'blob_sha1': 'e9b338a2b29dbf819791dc60791d45e994189109',
                                                                                                             'mode': '100644',
                                                                                                             'sha256': 'c9cff0f981af0b5cfe42d294ac0ff1e2089bf1b9ffe911cff95e64a36669621a',
                                                                                                             'size_bytes': 104060,
                                                                                                             'type': 'blob'},
                                    'tests/unit/deploy/test_final_source_refresh_transition.py': {'blob_sha1': '13e926bf2c79553a29bc03950748177c2b8e23ee',
                                                                                                  'mode': '100644',
                                                                                                  'sha256': '71483a5c99c78a99d8cb4dc0911cac72851f6cca68c4dabce275737cead0c2f0',
                                                                                                  'size_bytes': 133594,
                                                                                                  'type': 'blob'},
                                    'tests/unit/deploy/test_raw_report_transport.py': {'blob_sha1': '1896a56454ed844929f6afc6368378cba2e6c8c5',
                                                                                       'mode': '100644',
                                                                                       'sha256': '7096a6183c7b40a448557214e0ca33ac2f38ea90cfd363d5a724bba1bd5210ac',
                                                                                       'size_bytes': 17794,
                                                                                       'type': 'blob'},
                                    'tests/unit/deploy/test_raw_report_transport_source_profile.py': {'blob_sha1': '511b7b6125cdf833f9a9910f73cb110ed1ad0ffa',
                                                                                                      'mode': '100644',
                                                                                                      'sha256': '45b98df04d9f5e13265576dea80a14854f5eb69fd2bcd47b4c21f8228bfcd241',
                                                                                                      'size_bytes': 24295,
                                                                                                      'type': 'blob'},
                                    'tests/unit/deploy/test_shared_interpreter_rollback_preflight.py': {'blob_sha1': 'b488e3f142046655f0d88e4abdb7af7e3df95389',
                                                                                                        'mode': '100644',
                                                                                                        'sha256': '075704a88141c5f315b21729964da26fcf12bb8d0e7e33d7bf730b49c4944ae6',
                                                                                                        'size_bytes': 48748,
                                                                                                        'type': 'blob'},
                                    'tests/unit/deploy/test_shared_interpreter_source_profile.py': {'blob_sha1': '2810a6cf916a74a019806f9e9dad39f10a2b0a0f',
                                                                                                    'mode': '100644',
                                                                                                    'sha256': '9937ea081d425a879c00ecc694dda54e5c4a7b82912e8c47af921a5a12948cc7',
                                                                                                    'size_bytes': 39034,
                                                                                                    'type': 'blob'}}}}
_PURPOSE = "Historical public source bytes only; no authority for later code or deployment."


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Historical source archive repeats a field")
        result[key] = value
    return result


def load_historical_sources(path: Path | None = None) -> dict[str, dict[str, bytes]]:
    path = path or Path(__file__).parent / "fixtures/integration_historical_sources.json"
    archive = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    if (
        not isinstance(archive, dict)
        or set(archive) != {"schema_version", "purpose", "encoding", "archives"}
        or type(archive["schema_version"]) is not int
        or archive["schema_version"] != 1
        or archive["purpose"] != _PURPOSE
        or archive["encoding"] != "zlib-base64"
        or not isinstance(archive["archives"], dict)
        or set(archive["archives"]) != set(_PINNED_ARCHIVES)
    ):
        raise ValueError("Historical source archive has unknown roles or provenance")
    result = {}
    for name, pinned in _PINNED_ARCHIVES.items():
        group = archive["archives"][name]
        if (
            not isinstance(group, dict)
            or set(group) != {"source_commit", "source_tree", "sources"}
            or group["source_commit"] != pinned["source_commit"]
            or group["source_tree"] != pinned["source_tree"]
            or not isinstance(group["sources"], dict)
            or set(group["sources"]) != set(pinned["sources"])
        ):
            raise ValueError("Historical source archive changes reviewed identity or inventory")
        decoded = {}
        for source, expected in pinned["sources"].items():
            row = group["sources"][source]
            if (
                not isinstance(row, dict)
                or set(row) != {*expected, "zlib_base64_chunks"}
                or type(row.get("size_bytes")) is not int
                or any(row.get(key) != value for key, value in expected.items())
            ):
                raise ValueError("Historical source archive changes pinned metadata")
            chunks = row["zlib_base64_chunks"]
            if (
                not isinstance(chunks, list)
                or not 1 <= len(chunks) <= 8192
                or any(not isinstance(chunk, str) or not 1 <= len(chunk) <= 76 for chunk in chunks)
                or any(len(chunk) != 76 for chunk in chunks[:-1])
            ):
                raise ValueError("Historical source archive encoding is malformed")
            try:
                compressed = base64.b64decode("".join(chunks), validate=True)
                decoder = zlib.decompressobj()
                body = decoder.decompress(compressed, expected["size_bytes"] + 1)
            except (ValueError, zlib.error) as error:
                raise ValueError("Historical source archive encoding is malformed") from error
            blob = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
            if (
                len(body) != expected["size_bytes"]
                or not decoder.eof
                or decoder.unconsumed_tail
                or decoder.unused_data
                or hashlib.sha256(body).hexdigest() != expected["sha256"]
                or blob != expected["blob_sha1"]
            ):
                raise ValueError("Historical source archive differs from frozen source bytes")
            decoded[source] = body
        result[name] = decoded
    return result
