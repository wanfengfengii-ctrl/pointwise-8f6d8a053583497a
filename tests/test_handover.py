from dataclasses import replace
import json
import sqlite3

from exchange.catalog import BundleCatalog
from exchange.imports import import_bundle
from exchange.manifest import build_manifest, canonical_json, pack_bundle, unpack_bundle
from review.record_store import RecordStore
from review.retrieve import retrieve
from storage import connect
from survey.junctions import Junction
from survey.restrictions import Restriction
from survey.roads import Road
from tests.support import WorksiteTest, read_payload, reject_next_commit
from tiles.fragments import Fragment
from tiles.seams import SeamKey


class HandoverTests(WorksiteTest):
    def test_cross_tile_restriction_after_disconnect(self):
        revision = self.save()
        fixed = [self.publish(revision, plan) for plan in (self.single, self.split)]
        self.source.unlink()
        expected = (5, ('h', 'd', 'b', 'c'))
        records = []
        for (bundle_id, wire), plan in zip(fixed, (self.single, self.split)):
            with self.subTest(layout=plan.id):
                record = self.issue(self.accept((bundle_id, wire)))
                actual = record.itinerary.cost, record.itinerary.roads
                self.assertEqual(actual, expected, f'ROUTE_RESTRICTION_MISMATCH actual={actual!r} expected={expected!r}')
                self.assertEqual(retrieve(RecordStore(self.offline), record.id), record)
                self.assertEqual(record.request.bundle_id, bundle_id)
                records.append(record)
        if len(records) == len(fixed):
            print('POINTWISE_SCENARIO ' + json.dumps({
                'case_id': 'v4',
                'input': {'endpoints': ['X', 'T'], 'rule': ['a', 'b', 'c'], 'split_road': 'b',
                          'road_costs': {road.id: road.cost for road in self.roads}},
                'expected': [expected, expected],
                'actual': [(record.itinerary.cost, record.itinerary.roads) for record in records],
                'downstream_expected': [bundle_id for bundle_id, _ in fixed],
                'downstream_actual': [retrieve(RecordStore(self.offline), record.id).request.bundle_id for record in records],
                'code_paths': ['tiles/evidence.py', 'exchange/publish.py', 'exchange/imports.py',
                               'routing/search.py', 'review/issue.py', 'review/retrieve.py'],
                'oracle': 'Enumerate the two X-to-T routes by hand and remove the forbidden triple.',
            }, sort_keys=True))

    def test_rule_evidence_after_source_disconnect(self):
        fixed = self.publish(self.save(), self.split)
        self.source.unlink()
        bundle_id = self.accept(fixed)
        _, payload = read_payload(BundleCatalog(self.offline).find_accepted(bundle_id))
        self.assertEqual(len(payload.rules), 1)
        rule, = payload.rules
        self.assertEqual((rule.id, rule.roads), ('centre', ('a', 'b', 'c')))
        self.assertEqual(rule.fragment_refs, ((('west', 'a'),), (('west', 'b1'), ('east', 'b2')), (('east', 'c'),)))

    def test_same_physical_layout_different_rule(self):
        before = self.save()
        other = self.save(rules=(Restriction('centre', ('d', 'b', 'c')),))
        fixed = [(self.publish(before, plan), self.publish(other, plan)) for plan in (self.single, self.split)]
        self.source.unlink()
        for old, alternate in fixed:
            _, one = read_payload(old[1])
            _, two = read_payload(alternate[1])
            self.assertEqual(one.chains, two.chains)
            self.assertEqual(one.seams, two.seams)
            self.assertEqual([rule.roads for rule in one.rules], [('a', 'b', 'c')])
            self.assertEqual([rule.roads for rule in two.rules], [('d', 'b', 'c')])
            self.assert_itinerary(self.issue(self.accept(old)), 5, ('h', 'd', 'b', 'c'))
            self.assert_itinerary(self.issue(self.accept(alternate)), 4, ('a', 'b', 'c'))

    def test_reverse_roads_have_independent_restriction_identity(self):
        reverse = (Road('a_rev', 'J', 'X', 1), Road('b_rev', 'K', 'J', 2), Road('c_rev', 'T', 'K', 1))
        revision = self.save(roads=(*self.roads, *reverse))
        fixed = []
        for plan in (self.single, self.split):
            tile = plan.tiles[0]
            extra = tuple(Fragment(road.id, road.id, tile, 0, road.start, road.end, road.cost) for road in reverse)
            fixed.append(self.publish(revision, replace(plan, fragments=(*plan.fragments, *extra))))
        self.source.unlink()
        for bundle in fixed:
            bundle_id = self.accept(bundle)
            self.assert_itinerary(self.issue(bundle_id, 'T', 'X'), 4, ('c_rev', 'b_rev', 'a_rev'))
            self.assert_itinerary(self.issue(bundle_id, 'X', 'T'), 5, ('h', 'd', 'b', 'c'))

    def test_incomplete_bundle_rejected(self):
        healthy = self.publish(self.save(), self.split)
        healthy_id = self.accept(healthy)
        truncated = json.loads(healthy[1])
        truncated['payload']['fragments'].pop()
        with self.assertRaisesRegex(ValueError, 'manifest does not match'):
            import_bundle(self.accepted, canonical_json(truncated))
        self.assertEqual(self.bundle_ids(self.offline, 'accepted'), [healthy_id])
        self.assertEqual(self.accepted.find_accepted(healthy_id), healthy[1])
        self.assert_itinerary(self.issue(healthy_id), 5, ('h', 'd', 'b', 'c'))

    def test_matching_checksum_does_not_make_incomplete_chain_acceptable(self):
        healthy = self.publish(self.save(), self.split)
        healthy_id = self.accept(healthy)
        plan = replace(self.split, fragments=tuple(
            replace(part, cost={'b1': 2, 'b2': 0}[part.id]) if part.road_id == 'b' else part
            for part in self.split.fragments
        ))
        _, valid_wire = self.publish(self.save(rules=()), plan)
        original, encoded = unpack_bundle(valid_wire)
        document = json.loads(encoded)
        document['fragments'] = [part for part in document['fragments'] if part[0] != 'b2']
        broken_payload = canonical_json(document)
        manifest = build_manifest(original.revision_id, original.layout_id, broken_payload)
        broken_wire = pack_bundle(manifest, broken_payload)
        self.assertEqual(unpack_bundle(broken_wire), (manifest, broken_payload))
        with self.assertRaisesRegex(ValueError, 'incomplete or reversed fragment chain'):
            import_bundle(self.accepted, broken_wire)
        self.assertIsNone(self.accepted.find_accepted(manifest.bundle_id))
        self.assertEqual(self.bundle_ids(self.offline, 'accepted'), [healthy_id])
        self.assert_itinerary(self.issue(healthy_id), 5, ('h', 'd', 'b', 'c'))

    def test_reimport_identity_preserves_first_received_version(self):
        healthy = self.publish(self.save(), self.split)
        bundle_id = self.accept(healthy)
        equivalent_wire = json.dumps(json.loads(healthy[1]), indent=2).encode()
        self.assertEqual(import_bundle(self.accepted, equivalent_wire), bundle_id)
        original, encoded = unpack_bundle(healthy[1])
        document = json.loads(encoded)
        document['rules'] = []
        alternate = canonical_json(document)
        conflicting = build_manifest(original.revision_id, original.layout_id, alternate, bundle_id=bundle_id)
        alternate_wire = pack_bundle(conflicting, alternate)
        independent = BundleCatalog(self.root / 'independent.sqlite3')
        independent.initialize()
        self.assertEqual(import_bundle(independent, alternate_wire), bundle_id)
        with self.assertRaisesRegex(ValueError, 'another fixed bundle'):
            import_bundle(self.accepted, alternate_wire)
        self.assertEqual(self.bundle_ids(self.offline, 'accepted'), [bundle_id])
        self.assertEqual(self.accepted.find_accepted(bundle_id), healthy[1])
        self.assert_itinerary(self.issue(bundle_id), 5, ('h', 'd', 'b', 'c'))

    def test_shared_tail_different_eligibility(self):
        complete = self.direct_split_bundle()
        only_blocked_path = self.direct_split_bundle(include_alternative=False)
        self.source.unlink()
        bundle_id = self.accept(complete)
        self.assert_itinerary(self.issue(bundle_id), 5, ('h', 'd', 'b', 'c'))
        self.assert_itinerary(self.issue(bundle_id, 'Y', 'T'), 4, ('d', 'b', 'c'))
        unreachable = self.issue(self.accept(only_blocked_path))
        self.assert_itinerary(unreachable, None, None)
        self.assertEqual(retrieve(RecordStore(self.offline), unreachable.id), unreachable)

    def test_multiple_rules_preserve_overlapping_prefixes(self):
        junctions = (*self.junctions, Junction('W'), Junction('Z'))
        roads = (*self.roads, Road('q', 'K', 'W', 1), Road('z', 'T', 'Z', 1))
        rules = (*self.rules, Restriction('spur', ('a', 'b', 'q')), Restriction('overlap', ('b', 'c', 'z')))
        plan = replace(self.split, fragments=(*self.split.fragments,
                       Fragment('q', 'q', 'east', 0, 'K', 'W', 1), Fragment('z', 'z', 'east', 0, 'T', 'Z', 1)))
        bundle_id = self.accept(self.publish(self.save(junctions=junctions, roads=roads, rules=rules), plan))
        self.assert_itinerary(self.issue(bundle_id), 5, ('h', 'd', 'b', 'c'))
        self.assert_itinerary(self.issue(bundle_id, 'X', 'W'), 5, ('h', 'd', 'b', 'q'))
        self.assert_itinerary(self.issue(bundle_id, 'Y', 'Z'), None, None)

    def test_original_sequence_controls_ties(self):
        roads, (single, split) = self.adjusted_a(2)
        revision = self.save(roads=roads, rules=())
        changed = replace(split, id='renumbered', tiles=tuple(reversed(split.tiles)), fragments=tuple(
            replace(part, id=f'piece-{index}') for index, part in enumerate(reversed(split.fragments))
        ))
        for plan in (single, split, changed):
            bundle_id = self.accept(self.publish(revision, plan))
            self.assert_itinerary(self.issue(bundle_id), 5, ('a', 'b', 'c'))

    def test_endpoints_and_empty_path(self):
        bundle_id = self.accept(self.publish(self.save(), self.split))
        record = self.issue(bundle_id, 'X', 'X')
        self.assert_itinerary(record, 0, ())
        with self.assertRaises(KeyError):
            self.issue('missing')
        for bad in ('join', SeamKey('b', 'join'), None):
            with self.subTest(endpoint=bad), self.assertRaises(ValueError):
                self.issue(bundle_id, bad, 'T')
        self.assertEqual(self.record_ids(), [record.id])

    def test_issue_commit_failure(self):
        bundle_id = self.accept(self.publish(self.save(), self.split))
        first = self.issue(bundle_id)
        reject_next_commit(self.offline, 'review_records')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY'):
            self.issue(bundle_id, 'Y', 'T')
        reopened = RecordStore(self.offline)
        self.assertEqual(self.record_ids(), [first.id])
        self.assertEqual(retrieve(reopened, first.id), first)
        self.assertIsNone(retrieve(reopened, first.id + 1))
        with connect(self.offline) as database:
            self.assertEqual(database.execute('SELECT * FROM test_pending').fetchall(), [])
            database.execute('DROP TRIGGER test_reject_commit')
        retry = self.issue(bundle_id, 'Y', 'T')
        self.assert_itinerary(retry, 4, ('d', 'b', 'c'))
        self.assertEqual(retrieve(reopened, first.id), first)
