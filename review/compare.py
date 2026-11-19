from dataclasses import dataclass

from review.record_store import RecordStore, ReviewRecord
from review.retrieve import retrieve


@dataclass(frozen=True, slots=True)
class RecordComparison:
    before: ReviewRecord
    after: ReviewRecord
    reachability_changed: bool
    route_changed: bool
    cost_changed: bool


def compare(records: RecordStore, before_id: int, after_id: int) -> RecordComparison:
    before = retrieve(records, before_id)
    if before is None:
        raise KeyError(before_id)
    after = retrieve(records, after_id)
    if after is None:
        raise KeyError(after_id)
    if (before.request.start, before.request.end) != (after.request.start, after.request.end):
        raise ValueError('comparison requires the same ordered endpoint pair')
    return RecordComparison(
        before,
        after,
        before.itinerary.reachable != after.itinerary.reachable,
        before.itinerary.roads != after.itinerary.roads,
        before.itinerary.cost != after.itinerary.cost,
    )
