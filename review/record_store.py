from dataclasses import dataclass
import json

from review.requests import ReviewRequest
from routing.itineraries import Itinerary
from storage import DatabasePath, connect, is_row_id, write_transaction
from survey.roads import decode_cost, encode_cost


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    id: int
    request: ReviewRequest
    itinerary: Itinerary


class RecordStore:
    def __init__(self, path: DatabasePath):
        self.path = path

    def initialize(self) -> None:
        with connect(self.path) as database, write_transaction(database):
            database.execute('''
                CREATE TABLE IF NOT EXISTS review_records (
                    id INTEGER PRIMARY KEY,
                    bundle_id TEXT NOT NULL,
                    endpoints TEXT NOT NULL,
                    roads TEXT,
                    cost TEXT,
                    CHECK ((roads IS NULL) = (cost IS NULL))
                )
            ''')

    def commit(self, request: ReviewRequest, itinerary: Itinerary) -> ReviewRecord:
        endpoints = json.dumps((request.start, request.end))
        roads = None if itinerary.roads is None else json.dumps(itinerary.roads)
        cost = None if itinerary.cost is None else encode_cost(itinerary.cost)
        with connect(self.path) as database, write_transaction(database):
            cursor = database.execute(
                'INSERT INTO review_records(bundle_id, endpoints, roads, cost) VALUES (?, ?, ?, ?)',
                (request.bundle_id, endpoints, roads, cost),
            )
            record_id = cursor.lastrowid
        return ReviewRecord(record_id, request, itinerary)

    def get(self, record_id: int) -> ReviewRecord | None:
        if not is_row_id(record_id):
            return None
        with connect(self.path) as database:
            row = database.execute(
                'SELECT bundle_id, endpoints, roads, cost FROM review_records WHERE id = ?', (record_id,)
            ).fetchone()
        if row is None:
            return None
        bundle_id, encoded_endpoints, encoded_roads, encoded_cost = row
        start, end = json.loads(encoded_endpoints)
        roads = None if encoded_roads is None else tuple(json.loads(encoded_roads))
        cost = None if encoded_cost is None else decode_cost(encoded_cost)
        return ReviewRecord(record_id, ReviewRequest(bundle_id, start, end), Itinerary(roads, cost))
