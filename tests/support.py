from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from demo import load_sample
from exchange.catalog import BundleCatalog
from exchange.imports import import_bundle
from exchange.manifest import build_manifest, pack_bundle, unpack_bundle
from exchange.payload import BundlePayload, decode_payload, encode_payload
from exchange.publish import publish
from review.issue import issue
from review.record_store import RecordStore
from review.requests import ReviewRequest
from storage import connect
from survey.revision_store import RevisionStore
from survey.revisions import save_revision
from tiles.evidence import RuleEvidence
from tiles.fragments import assemble_fragment_chains


class WorksiteTest(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='chengwan-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source.sqlite3'
        self.offline = self.root / 'offline.sqlite3'
        self.revisions = RevisionStore(self.source)
        self.published = BundleCatalog(self.source)
        self.accepted = BundleCatalog(self.offline)
        self.records = RecordStore(self.offline)
        for store in (self.revisions, self.published, self.accepted, self.records):
            store.initialize()
        self.junctions, self.roads, self.rules, self.plans = load_sample()
        self.single, self.split = self.plans['single'], self.plans['split']

    def save(self, *, junctions=None, roads=None, rules=None):
        return save_revision(
            self.revisions,
            self.junctions if junctions is None else junctions,
            self.roads if roads is None else roads,
            self.rules if rules is None else rules,
        )

    def publish(self, revision_id, plan):
        return publish(self.revisions, self.published, revision_id, plan)

    def accept(self, bundle):
        bundle_id, wire = bundle
        self.assertEqual(import_bundle(self.accepted, wire), bundle_id)
        return bundle_id

    def issue(self, bundle_id, start='X', end='T'):
        return issue(self.accepted, self.records, ReviewRequest(bundle_id, start, end))

    def assert_itinerary(self, record, cost, roads):
        self.assertEqual(record.itinerary.reachable, roads is not None)
        self.assertEqual((record.itinerary.cost, record.itinerary.roads), (cost, roads))

    def revision_ids(self):
        with connect(self.source) as database:
            return [row[0] for row in database.execute('SELECT id FROM revisions ORDER BY id')]

    def bundle_ids(self, path, stage):
        with connect(path) as database:
            return [row[0] for row in database.execute(
                'SELECT bundle_id FROM fixed_bundles WHERE stage = ? ORDER BY bundle_id', (stage,)
            )]

    def record_ids(self):
        with connect(self.offline) as database:
            return [row[0] for row in database.execute('SELECT id FROM review_records ORDER BY id')]

    def adjusted_a(self, cost):
        roads = tuple(replace(road, cost=cost) if road.id == 'a' else road for road in self.roads)
        plans = tuple(replace(plan, fragments=tuple(
            replace(fragment, cost=cost) if fragment.road_id == 'a' else fragment for fragment in plan.fragments
        )) for plan in (self.single, self.split))
        return roads, plans

    def direct_split_bundle(self, include_alternative=True):
        roads = tuple(road for road in self.roads if include_alternative or road.id != 'h')
        fragments = tuple(part for part in self.split.fragments if include_alternative or part.road_id != 'h')
        # The intended references are fixed by the fixture, independently of publication.
        rule = RuleEvidence('centre', ('a', 'b', 'c'), (
            (('west', 'a'),), (('west', 'b1'), ('east', 'b2')), (('east', 'c'),),
        ))
        payload = BundlePayload(self.junctions, roads, self.split.tiles, self.split.seams,
                                assemble_fragment_chains(fragments), (rule,))
        encoded = encode_payload(payload)
        manifest = build_manifest(41, self.split.id, encoded)
        return manifest.bundle_id, pack_bundle(manifest, encoded)


def read_payload(wire):
    manifest, encoded = unpack_bundle(wire)
    return manifest, decode_payload(encoded)


def reject_next_commit(path, table, condition='1'):
    if table not in ('fixed_bundles', 'review_records'):
        raise ValueError(table)
    with connect(path) as database:
        database.executescript(f'''
            CREATE TABLE test_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE test_pending (
                target INTEGER REFERENCES test_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TRIGGER test_reject_commit AFTER INSERT ON {table} WHEN {condition}
            BEGIN
                INSERT INTO test_pending(target) VALUES (42);
            END;
        ''')
