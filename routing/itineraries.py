from dataclasses import dataclass

from exchange.payload import BundlePayload
from routing.network import build_network
from routing.permissions import compile_permissions
from routing.search import find_shortest_route


@dataclass(frozen=True, slots=True)
class Itinerary:
    roads: tuple[str, ...] | None
    cost: int | None

    @property
    def reachable(self) -> bool:
        return self.roads is not None


def calculate_itinerary(payload: BundlePayload, start: str, end: str) -> Itinerary:
    network = build_network(payload)
    policy = compile_permissions(payload.rules)
    route = find_shortest_route(network, policy, start, end)
    if route is None:
        return Itinerary(None, None)
    return Itinerary(route, sum(network.by_road[road_id].cost for road_id in route))
