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


def _rules_in_sheet_catalog(
    restrictions: Iterable[Restriction], chains: Iterable[FragmentChain]
) -> tuple[Restriction, ...]:
    sheets = {}
    for chain in chains:
        tiles = {part.tile_id for part in chain.fragments}
        if len(tiles) == 1:
            sheets[chain.road_id] = next(iter(tiles))
    return tuple(
        rule for rule in restrictions
        if all(road in sheets for road in rule.roads)
        and len({sheets[road] for road in rule.roads}) == 1
    )


def build_rule_evidence(
    restrictions: Iterable[Restriction], chains: Iterable[FragmentChain]
) -> tuple[RuleEvidence, ...]:
    chains = tuple(chains)
    by_road = {chain.road_id: chain.refs for chain in chains}
    local = _rules_in_sheet_catalog(restrictions, chains)
    return tuple(
        RuleEvidence(rule.id, rule.roads, tuple(by_road[road] for road in rule.roads))
        for rule in sorted(local, key=lambda rule: rule.id)
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
        expected = _rules_in_sheet_catalog(validate_restrictions(expected_rules, roads), chains)
        if actual != expected:
            raise ValueError('rule evidence does not cover the selected revision')
    by_road = {chain.road_id: chain.refs for chain in chains}
    for rule in rules:
        if any(road not in by_road for road in rule.roads):
            raise ValueError(f'missing fragment chain for rule {rule.id!r}')
        references = tuple(by_road[road] for road in rule.roads)
        if references != rule.fragment_refs:
            raise ValueError(f'fragment evidence disagrees with directed road order for rule {rule.id!r}')
