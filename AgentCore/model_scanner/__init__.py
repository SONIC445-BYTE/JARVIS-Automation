"""
LLM coding-benchmark scanner.

Informs the developer-configured model slot in Adaptive Adapter
Generation (§4.4b). Data class: `general` (§3.7b) -- see
docs/model_benchmark_scanner.md for the classification and its
justification. Recommends only; never selects.
"""
from .classification import Licensing, classify
from .scanner import (
    AIDER_POLYGLOT_URL,
    BenchmarkSourceError,
    ModelResult,
    ScanResult,
    scan,
)

__all__ = [
    "AIDER_POLYGLOT_URL",
    "BenchmarkSourceError",
    "Licensing",
    "ModelResult",
    "ScanResult",
    "classify",
    "scan",
]
