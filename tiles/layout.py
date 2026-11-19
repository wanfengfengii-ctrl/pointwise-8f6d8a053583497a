from collections.abc import Iterable
from dataclasses import dataclass

from survey.junctions import require_name
from survey.revisions import Revision
from tiles.costs import verify_chain_costs
from tiles.evidence import RuleEvidence, build_rule_evidence, validate_rule_evidence
from tiles.fragments import Fragment, FragmentChain, assemble_fragment_chains, validate_fragment_chains
from tiles.seams import Seam, index_seams


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    id: str
    tiles: tuple[str, ...]
    seams: tuple[Seam, ...]
    fragments: tuple[Fragment, ...]


@dataclass(frozen=True, slots=True)
class PreparedLayout:
    id: str
    tiles: tuple[str, ...]
    seams: tuple[Seam, ...]
    chains: tuple[FragmentChain, ...]
    rules: tuple[RuleEvidence, ...]


def validate_tiles(tiles: Iterable[str]) -> tuple[str, ...]:
    if isinstance(tiles, str):
        raise ValueError('tiles must be a collection of names')
    names = tuple(require_name(tile, 'tile id') for tile in tiles)
    if not names or len(set(names)) != len(names):
        raise ValueError('layout requires distinct named tiles')
    return tuple(sorted(names))


def prepare_layout(revision: Revision, plan: LayoutPlan) -> PreparedLayout:
    if not isinstance(plan, LayoutPlan):
        raise ValueError('expected a LayoutPlan')
    name = require_name(plan.id, 'layout id')
    roads = {road.id: road for road in revision.roads}
    try:
        tiles = validate_tiles(plan.tiles)
        seams = index_seams(plan.seams, roads)
        chains = assemble_fragment_chains(plan.fragments)
    except TypeError as error:
        raise ValueError('layout requires tile, seam and fragment declarations') from error
    validate_fragment_chains(roads, set(tiles), seams, chains)
    verify_chain_costs(roads, chains)
    restrictions = revision.restrictions
    evidence = build_rule_evidence(restrictions, chains)
    validate_rule_evidence(evidence, roads, chains, expected_rules=restrictions)
    ordered_seams = tuple(seams[key] for key in sorted(seams, key=lambda key: (key.road_id, key.id)))
    return PreparedLayout(name, tiles, ordered_seams, chains, evidence)
