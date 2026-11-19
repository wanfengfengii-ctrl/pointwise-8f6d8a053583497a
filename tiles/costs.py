from collections.abc import Iterable, Mapping

from survey.roads import Road
from tiles.fragments import Fragment, FragmentChain


def sum_fragment_costs(fragments: Iterable[Fragment]) -> int:
    return sum(fragment.cost for fragment in fragments)


def verify_chain_costs(roads: Mapping[str, Road], chains: Iterable[FragmentChain]) -> None:
    for chain in chains:
        expected = roads[chain.road_id].cost
        actual = sum_fragment_costs(chain.fragments)
        if actual != expected:
            raise ValueError(f'fragment cost differs from original cost for road {chain.road_id!r}')
