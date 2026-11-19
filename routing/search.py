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
    # A state is the current endpoint together with every original directed road
    # completed so far: arriving at the same junction with different history can
    # grant different passage, and legal routes may revisit junctions.
    start_state = (start, ())
    queue = [(0, (), next(order), start_state)]
    best = {start_state: (0, ())}
    while queue:
        cost, route, _, (endpoint, history) = heappop(queue)
        if best[(endpoint, history)] != (cost, route):
            continue
        if endpoint == end:
            # Heap order is total cost then lexicographic road sequence, so the
            # first state popped at the target is the required shortest route.
            return route
        for fragment in network.outgoing.get(endpoint, ()):
            if fragment.ordinal == 0 and not check_passage(policy, history, fragment.road_id):
                continue
            candidate_cost, candidate_route = cost, route
            candidate_history = history
            if fragment.ordinal == 0:
                # Charge the verified road total once, at entry to its forced chain.
                candidate_cost += network.by_road[fragment.road_id].cost
                candidate_route = (*route, fragment.road_id)
            if fragment.ordinal == network.last_ordinal[fragment.road_id]:
                # The original directed road is only complete after its final
                # fragment; interior seam points belong to this chain alone.
                candidate_history = (*history, fragment.road_id)
            destination_state = (fragment.end, candidate_history)
            candidate = candidate_cost, candidate_route
            if destination_state not in best or candidate < best[destination_state]:
                best[destination_state] = candidate
                heappush(queue, (*candidate, next(order), destination_state))
    return None
