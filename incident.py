import json
from pathlib import Path
from tempfile import TemporaryDirectory

from demo import load_sample
from exchange.catalog import BundleCatalog
from exchange.imports import import_bundle
from exchange.publish import publish
from review.issue import issue
from review.record_store import RecordStore
from review.requests import ReviewRequest
from survey.restrictions import Restriction
from survey.revision_store import RevisionStore
from survey.revisions import save_revision


EXPECTED = {
    "centre": {"cost": 5, "roads": ["h", "d", "b", "c"]},
    "alternate": {"cost": 4, "roads": ["a", "b", "c"]},
}


def main() -> int:
    junctions, roads, rules, plans = load_sample()
    with TemporaryDirectory(prefix="chengwan-incident-") as directory:
        source = Path(directory) / "survey.sqlite3"
        offline = Path(directory) / "review.sqlite3"
        revisions, published = RevisionStore(source), BundleCatalog(source)
        accepted, records = BundleCatalog(offline), RecordStore(offline)
        for store in (revisions, published, accepted, records):
            store.initialize()

        cases = (("centre", rules), ("alternate", (Restriction("centre", ("d", "b", "c")),)))
        bundles = {}
        for label, restrictions in cases:
            revision = save_revision(revisions, junctions, roads, restrictions)
            bundles[label] = publish(revisions, published, revision, plans["split"])
        source.unlink()

        actual = {}
        for label, (bundle_id, wire) in bundles.items():
            if import_bundle(accepted, wire) != bundle_id:
                raise AssertionError("accepted the wrong package")
            itinerary = issue(accepted, records, ReviewRequest(bundle_id, "X", "T")).itinerary
            actual[label] = {
                "cost": itinerary.cost,
                "roads": None if itinerary.roads is None else list(itinerary.roads),
            }

    print(json.dumps({"expected": EXPECTED, "actual": actual}, sort_keys=True))
    if actual != EXPECTED:
        print("ROUTE_RESTRICTION_MISMATCH")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
