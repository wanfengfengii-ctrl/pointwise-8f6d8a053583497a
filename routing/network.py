from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from exchange.payload import BundlePayload
from survey.roads import Road
from tiles.fragments import Fragment
from tiles.seams import Endpoint


@dataclass(frozen=True, slots=True)
class RoutingNetwork:
    junctions: frozenset[str]
    outgoing: Mapping[Endpoint, tuple[Fragment, ...]]
    by_road: Mapping[str, Road]


def build_network(payload: BundlePayload) -> RoutingNetwork:
    outgoing = defaultdict(list)
    for chain in payload.chains:
        for fragment in chain.fragments:
            outgoing[fragment.start].append(fragment)
    return RoutingNetwork(
        frozenset(junction.id for junction in payload.junctions),
        MappingProxyType({endpoint: tuple(parts) for endpoint, parts in outgoing.items()}),
        MappingProxyType({road.id: road for road in payload.roads}),
    )
