from exchange.catalog import BundleCatalog
from exchange.manifest import unpack_bundle
from exchange.payload import decode_payload
from review.record_store import RecordStore, ReviewRecord
from review.requests import ReviewRequest, validate_request
from routing.itineraries import calculate_itinerary


def issue(catalog: BundleCatalog, records: RecordStore, request: ReviewRequest) -> ReviewRecord:
    if not isinstance(request, ReviewRequest):
        raise ValueError('expected a ReviewRequest')
    wire = catalog.find_accepted(request.bundle_id)
    if wire is None:
        raise KeyError(request.bundle_id)
    manifest, encoded = unpack_bundle(wire)
    if manifest.bundle_id != request.bundle_id:
        raise ValueError('accepted bundle does not match the requested id')
    payload = decode_payload(encoded)
    validate_request(request, payload)
    itinerary = calculate_itinerary(payload, request.start, request.end)
    return records.commit(request, itinerary)
