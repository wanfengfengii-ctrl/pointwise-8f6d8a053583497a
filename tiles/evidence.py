from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from survey.restrictions import Restriction, validate_restrictions
from survey.roads import Road
from tiles.fragments import FragmentChain, FragmentRef


@dataclass(frozen=True, slots=True)
class RuleEvidence:
    id: str
    roads: tuple[str, str, str]
    fragment_refs: tuple[tuple[FragmentRef, ...], ...]


def build_rule_evidence(
    restrictions: Iterable[Restriction], chains: Iterable[FragmentChain]
) -> tuple[RuleEvidence, ...]:
    # Every named rule must survive a re-tiling: a restriction is judged on the
    # three consecutively completed original directed roads, regardless of which
    # sheets their ordered fragment groups happen to live on.
    chains = tuple(chains)
    by_road = {chain.road_id: chain.refs for chain in chains}
    return tuple(
        RuleEvidence(rule.id, rule.roads, tuple(by_road[road] for road in rule.roads))
        for rule in sorted(tuple(restrictions), key=lambda rule: rule.id)
    )


def validate_rule_evidence(
    evidence: Iterable[RuleEvidence],
    roads: Mapping[str, Road],
    chains: Iterable[FragmentChain],
    expected_rules: Iterable[Restriction] | None = None,
) -> None:
    chains = tuple(chains)
    rules = tuple(evidence)
    actual = validate_restrictions((Restriction(rule.id, rule.roads) for rule in rules), roads)
    if expected_rules is not None:
        expected = validate_restrictions(expected_rules, roads)
        if actual != expected:
            raise ValueError('rule evidence does not cover the selected revision')
    by_road = {chain.road_id: chain.refs for chain in chains}
    for rule in rules:
        if any(road not in by_road for road in rule.roads):
            raise ValueError(f'missing fragment chain for rule {rule.id!r}')
        references = tuple(by_road[road] for road in rule.roads)
        if references != rule.fragment_refs:
            raise ValueError(f'fragment evidence disagrees with directed road order for rule {rule.id!r}')
