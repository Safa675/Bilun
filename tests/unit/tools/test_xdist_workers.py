from tests.fixtures.xdist_workers import auto_workers, cgroup_memory_limit

GB = 1024**3


def test_the_worker_count_fits_the_memory_limit():
    assert auto_workers(8, {}, limit=10 * GB) == 5  # the VPS runner
    assert auto_workers(8, {}, limit=16 * GB) == 8  # the laptop runner, unchanged
    assert auto_workers(8, {}, limit=None) == 8  # no limit
    assert auto_workers(8, {}, limit=GB) == 1
    assert auto_workers(3, {"PYTEST_XDIST_AUTO_NUM_WORKERS": "3"}, limit=GB) == 3


def test_the_limit_is_read_from_the_process_cgroup(tmp_path):
    proc = tmp_path / "cgroup"
    proc.write_text("0::/\n")
    (tmp_path / "memory.max").write_text("10737418240\n")
    assert cgroup_memory_limit(proc, tmp_path) == 10 * GB
    (tmp_path / "memory.max").write_text("max\n")
    assert cgroup_memory_limit(proc, tmp_path) is None
    assert cgroup_memory_limit(tmp_path / "missing", tmp_path) is None
