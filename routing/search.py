from heapq import heappop, heappush
from itertools import count

from routing.network import RoutingNetwork
from routing.permissions import RestrictionPolicy, check_passage


def find_shortest_route(
    network: RoutingNetwork, policy: RestrictionPolicy, start: str, end: str
) -> tuple[str, ...] | None:
    if start not in network.junctions or end not in network.junctions:
        raise ValueError("route endpoints must be real junctions in the selected bundle")
    order = count()
    queue = [(0, (), next(order), start, ())]
    best = {start: (0, ())}
    while queue:
        cost, route, _, endpoint, pieces = heappop(queue)
        if best[endpoint] != (cost, route):
            continue
        if endpoint == end:
            return route
        for fragment in network.outgoing.get(endpoint, ()):
            if not check_passage(policy, pieces, fragment.ref):
                continue
            candidate_cost, candidate_route = cost, route
            if fragment.ordinal == 0:
                # Charge the verified road total once, at entry to its forced chain.
                candidate_cost += network.by_road[fragment.road_id].cost
                candidate_route = (*route, fragment.road_id)
            destination = fragment.end
            candidate = candidate_cost, candidate_route
            if destination not in best or candidate < best[destination]:
                best[destination] = candidate
                heappush(queue, (*candidate, next(order), destination, (*pieces, fragment.ref)))
    return None
