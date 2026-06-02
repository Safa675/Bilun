"""SUT main-document (prose) extraction and coverage utilities."""

from .coverage import build_sut_coverage, write_sut_coverage
from .extractor import SutClauseExtractor, extract_sut_clauses
from .rule_registry import RULE_REGISTRY, RuleRegistryEntry

__all__ = [
    "SutClauseExtractor",
    "extract_sut_clauses",
    "build_sut_coverage",
    "write_sut_coverage",
    "RULE_REGISTRY",
    "RuleRegistryEntry",
]
