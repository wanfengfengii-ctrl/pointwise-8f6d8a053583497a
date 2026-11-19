from review.record_store import RecordStore, ReviewRecord


def retrieve(records: RecordStore, record_id: int) -> ReviewRecord | None:
    return records.get(record_id)
