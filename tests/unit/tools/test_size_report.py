from tools.size_report import tally


def test_lines_are_summed_per_area_and_binary_files_skipped():
    numstat = "\n".join([
        "10\t2\tsrc/bilun/a.py",
        "30\t0\ttests/unit/test_a.py",
        "5\t5\tfrontend/src/lib/x.test.ts",
        "-\t-\tdata/blob.parquet",
        "1\t1\tREADME.md",
    ])
    assert tally(numstat) == {
        "src": [10, 2],
        "tests": [30, 0],
        "frontend tests": [5, 5],
        "other": [1, 1],
    }
