from collections import defaultdict
from collections.abc import Iterable, Mapping

from tiles.evidence import RuleEvidence
from tiles.fragments import FragmentRef


RestrictionPolicy = Mapping[FragmentRef, tuple[tuple[FragmentRef, ...], ...]]


def compile_permissions(evidence: Iterable[RuleEvidence]) -> RestrictionPolicy:
    by_exit = defaultdict(list)
    for rule in evidence:
        sequence = tuple(ref for group in rule.fragment_refs for ref in group)
        if len({tile for tile, _ in sequence}) == 1:
            by_exit[sequence[-1]].append(sequence[:-1])
    return {ref: tuple(prefixes) for ref, prefixes in by_exit.items()}


def check_passage(policy: RestrictionPolicy, pieces: tuple[FragmentRef, ...], ref: FragmentRef) -> bool:
    return all(pieces[-len(prefix):] != prefix for prefix in policy.get(ref, ()))
