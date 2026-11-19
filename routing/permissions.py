from collections import defaultdict
from collections.abc import Iterable, Mapping

from tiles.evidence import RuleEvidence


# For each original directed road that would complete a forbidden passage, the
# ordered pairs of preceding original roads that make entering it illegal.
RestrictionPolicy = Mapping[str, tuple[tuple[str, str], ...]]


def compile_permissions(evidence: Iterable[RuleEvidence]) -> RestrictionPolicy:
    by_exit = defaultdict(list)
    for rule in evidence:
        first, middle, last = rule.roads
        by_exit[last].append((first, middle))
    return {road_id: tuple(prefixes) for road_id, prefixes in by_exit.items()}


def check_passage(
    policy: RestrictionPolicy, completed_roads: tuple[str, ...], road_id: str
) -> bool:
    # Restrictions fire only once the three original directed roads have all
    # been completed, so only the two most recent completions can matter.
    prefix = completed_roads[-2:]
    return all(prefix != forbidden for forbidden in policy.get(road_id, ()))
