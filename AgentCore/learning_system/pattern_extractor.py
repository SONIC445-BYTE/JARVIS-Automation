"""
Pattern Extractor — Cluster and generalise action sequences
=============================================================
Groups similar step sequences and replaces literals with
parameterised templates (e.g. contact name → {contact}).
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ── data models ──────────────────────────────────────────────

@dataclass
class Sequence:
    """Ordered list of atomic step tokens."""
    tokens: List[str]
    context: Dict = field(default_factory=dict)
    source_session: str = ''


@dataclass
class Cluster:
    """Group of similar sequences."""
    cluster_id: str
    sequences: List[Sequence] = field(default_factory=list)
    representative: Optional[List[str]] = None

    @property
    def size(self) -> int:
        return len(self.sequences)


@dataclass
class ActionTemplate:
    """Generalised, parameterised action template."""
    template_id: str
    name: str
    description: str
    steps: List[Dict]        # [{"op": "open_app", "args": {"app": "{app}"}}, ...]
    parameters: List[str]    # ["{contact}", "{position}"]
    source_cluster_id: str = ''
    example_count: int = 0


# ── helpers ──────────────────────────────────────────────────

def _edit_distance(a: List[str], b: List[str]) -> int:
    """Levenshtein distance over token lists."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            ins = dp[j] + 1
            dele = dp[j - 1] + 1
            sub = prev + (0 if a[i - 1] == b[j - 1] else 1)
            prev = dp[j]
            dp[j] = min(ins, dele, sub)
    return dp[n]


def _normalised_distance(a: List[str], b: List[str]) -> float:
    """0 = identical, 1 = completely different."""
    if not a and not b:
        return 0.0
    return _edit_distance(a, b) / max(len(a), len(b))


# ── main class ───────────────────────────────────────────────

class PatternExtractor:
    """Cluster sequences and generalise into templates."""

    def __init__(self, similarity_threshold: float = 0.4):
        """
        Args:
            similarity_threshold: Maximum normalised edit distance
                for two sequences to be in the same cluster.
        """
        self._threshold = similarity_threshold

    def cluster_sequences(self, sequences: List[Sequence]) -> List[Cluster]:
        """
        Group sequences by pairwise similarity using single-link
        agglomerative clustering with edit distance.

        Returns a list of Clusters.
        """
        if not sequences:
            return []

        assigned = [False] * len(sequences)
        clusters: List[Cluster] = []
        cid = 0

        for i, seq_i in enumerate(sequences):
            if assigned[i]:
                continue
            cluster = Cluster(cluster_id=f"cluster_{cid}")
            cluster.sequences.append(seq_i)
            assigned[i] = True
            for j in range(i + 1, len(sequences)):
                if assigned[j]:
                    continue
                dist = _normalised_distance(seq_i.tokens, sequences[j].tokens)
                if dist <= self._threshold:
                    cluster.sequences.append(sequences[j])
                    assigned[j] = True
            # pick the most common sequence as representative
            cluster.representative = self._pick_representative(cluster.sequences)
            clusters.append(cluster)
            cid += 1

        return clusters

    def generalize_cluster(self, cluster: Cluster) -> ActionTemplate:
        """
        Generalise a cluster into a parameterised ActionTemplate.

        Tokens that vary across sequences in the cluster are
        replaced with parameter placeholders like {param_0}.
        """
        if not cluster.sequences:
            return ActionTemplate(
                template_id=f"tmpl_{cluster.cluster_id}",
                name="empty",
                description="Empty template",
                steps=[],
                parameters=[],
                source_cluster_id=cluster.cluster_id,
            )

        rep = cluster.representative or cluster.sequences[0].tokens
        params: List[str] = []
        generalised_steps: List[Dict] = []

        for idx, token in enumerate(rep):
            # check if this position varies across sequences
            varies = False
            for seq in cluster.sequences:
                if idx < len(seq.tokens) and seq.tokens[idx] != token:
                    varies = True
                    break

            if varies:
                param_name = f"{{param_{len(params)}}}"
                params.append(param_name)
                generalised_steps.append({
                    'op': 'parameterised',
                    'token': param_name,
                    'default': token,
                })
            else:
                generalised_steps.append({'op': token})

        name = '_'.join(rep[:3]) if rep else 'unknown'
        return ActionTemplate(
            template_id=f"tmpl_{cluster.cluster_id}",
            name=name,
            description=f"Generalised from {cluster.size} sequences",
            steps=generalised_steps,
            parameters=params,
            source_cluster_id=cluster.cluster_id,
            example_count=cluster.size,
        )

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _pick_representative(sequences: List[Sequence]) -> List[str]:
        """Return the token list that appears most often."""
        from collections import Counter
        counts = Counter(tuple(s.tokens) for s in sequences)
        best = counts.most_common(1)[0][0]
        return list(best)
