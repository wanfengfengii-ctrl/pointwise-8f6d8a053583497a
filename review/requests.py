from dataclasses import dataclass

from exchange.payload import BundlePayload
from survey.junctions import require_name


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    bundle_id: str
    start: str
    end: str


def validate_request(request: ReviewRequest, payload: BundlePayload) -> None:
    require_name(request.bundle_id, 'bundle id')
    start = require_name(request.start, 'start junction')
    end = require_name(request.end, 'end junction')
    junctions = {junction.id for junction in payload.junctions}
    if start not in junctions or end not in junctions:
        raise ValueError('review endpoints must be real junctions in the selected bundle')
