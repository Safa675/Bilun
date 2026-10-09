"""Default-lane import coverage for deploy modules used by the product."""

from importlib import import_module


def test_product_release_dependencies_remain_importable():
    required_symbols = {
        "scripts.deploy.release_sidecar": (
            "ReleaseSidecarExpectation", "_load_private_json", "verify_release_sidecar",
        ),
        "scripts.deploy.verify_private_rehearsal": ("verify_private_rehearsal",),
        "scripts.deploy.verify_candidate_cache": ("_candidate_db_hash", "_stable_file_hash"),
        "scripts.deploy.serving_activation": ("load_serving_activation",),
        "src.bilun.api.wavea_activation": ("load_startup_activation", "set_startup_activation"),
        "src.bilun.api.startup": ("startup",),
    }
    for module_name, symbols in required_symbols.items():
        module = import_module(module_name)
        for symbol in symbols:
            assert callable(getattr(module, symbol)), f"{module_name}.{symbol} must remain callable"
