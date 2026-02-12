"""
Optimization Metrics for Level-5 Meta-Learning.
Defines the cost function for self-evolution.
"""
from typing import Dict

DEFAULT_WEIGHTS = {
    "stability": 0.5,    # Crash rate, error rate
    "speed": 0.2,        # Execution time
    "quality": 0.3       # Code style, complexity score
}

def calculate_score(metrics: Dict[str, float], weights: Dict[str, float] = DEFAULT_WEIGHTS) -> float:
    """
    Calculate composite optimization score.
    Higher is better.
    """
    score = 0.0
    score += (1.0 - metrics.get("error_rate", 0.0)) * weights["stability"]
    score += (1.0 / (1.0 + metrics.get("execution_time", 0.0))) * weights["speed"]
    score += metrics.get("code_quality", 0.0) * weights["quality"]
    return score
