from dataclasses import replace
import sqlite3

from exchange.catalog import BundleCatalog
from review.record_store import RecordStore
from review.retrieve import retrieve
from survey.junctions import Junction
from survey.restrictions import Restriction
from survey.revisions import load_revision
from survey.roads import Road
from tests.support import WorksiteTest, read_payload, reject_next_commit
from tiles.fragments import Fragment
from tiles.layout import LayoutPlan
from tiles.seams import Seam, SeamKey


class PrepareTests(WorksiteTest):
    def test_partition_preserves_cost_and_provenance(self):
        revision = self.save()
        for plan, expected_refs in (
            (self.single, (('sheet', 'b'),)),
            (self.split, (('west', 'b1'), ('east', 'b2'))),
        ):
            with self.subTest(layout=plan.id):
                bundle_id, wire = self.publish(revision, plan)
                self.assertEqual(self.published.find_published(bundle_id), wire)
                manifest, payload = read_payload(wire)
                self.assertEqual((manifest.revision_id, manifest.layout_id), (revision, plan.id))
                self.assertEqual({chain.road_id for chain in payload.chains}, {'a', 'b', 'c', 'd', 'h'})
                bridge = next(chain for chain in payload.chains if chain.road_id == 'b')
                self.assertEqual(bridge.refs, expected_refs)
                self.assertEqual(sum(part.cost for part in bridge.fragments), 2)
                self.assertEqual({part.road_id for part in bridge.fragments}, {'b'})
                self.assertEqual((bridge.fragments[0].start, bridge.fragments[-1].end), ('J', 'K'))

    def test_coincident_seams_stay_on_their_directed_chains(self):
        junctions = tuple(Junction(name) for name in ('X', 'J', 'K', 'T'))
        roads = (Road('one', 'X', 'J', 2), Road('two', 'K', 'T', 2))
        revision = self.save(junctions=junctions, roads=roads, rules=())
        first, second = SeamKey('one', 'J'), SeamKey('two', 'J')
        for coordinate in (4, 7):
            plan = LayoutPlan(
                f'pair-{coordinate}', ('west', 'east'), (Seam(first, 4, 2), Seam(second, coordinate, 2)), (
                    Fragment('one', 'one', 'west', 0, 'X', first, 1),
                    Fragment('one', 'one', 'east', 1, first, 'J', 1),
                    Fragment('two', 'two', 'west', 0, 'K', second, 1),
                    Fragment('two', 'two', 'east', 1, second, 'T', 1),
                ),
            )
            fixed = self.publish(revision, plan)
            _, payload = read_payload(fixed[1])
            self.assertEqual({seam.key for seam in payload.seams}, {first, second})
            self.assertEqual([chain.fragments[0].end for chain in payload.chains], [first, second])
            bundle_id = self.accept(fixed)
            self.assert_itinerary(self.issue(bundle_id, 'X', 'J'), 2, ('one',))
            self.assert_itinerary(self.issue(bundle_id, 'K', 'T'), 2, ('two',))
            self.assert_itinerary(self.issue(bundle_id, 'X', 'T'), None, None)

    def test_exact_integer_cost_survives_publication_and_records(self):
        total = 9223372036854775809
        road = Road('b', 'J', 'K', total)
        revision = self.save(junctions=(Junction('J'), Junction('K')), roads=(road,), rules=())
        self.assertEqual(load_revision(self.revisions, revision).roads, (road,))
        key = SeamKey('b', 'join')
        single = LayoutPlan('single', ('west',), (), (Fragment('b', 'b', 'west', 0, 'J', 'K', total),))
        split = LayoutPlan('split', ('west', 'east'), (Seam(key, 4, 2),), (
            Fragment('p', 'b', 'west', 0, 'J', key, 4611686018427387904),
            Fragment('q', 'b', 'east', 1, key, 'K', 4611686018427387905),
        ))
        for plan, costs in ((single, [total]), (split, [4611686018427387904, 4611686018427387905])):
            bundle_id, wire = self.publish(revision, plan)
            self.assertEqual(BundleCatalog(self.source).find_published(bundle_id), wire)
            _, payload = read_payload(wire)
            self.assertEqual([part.cost for part in payload.chains[0].fragments], costs)
            self.assertEqual(sum(part.cost for part in payload.chains[0].fragments), total)
            record = self.issue(self.accept((bundle_id, wire)), 'J', 'K')
            stored = retrieve(RecordStore(self.offline), record.id)
            self.assertEqual(stored, record)
            self.assert_itinerary(stored, total, ('b',))

    def test_disconnected_rule_rejected(self):
        revision = self.save()
        for sequence in (('a', 'c', 'b'), ('a', 'b', 'missing')):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                self.save(rules=(Restriction('invalid', sequence),))
        self.assertEqual(self.revision_ids(), [revision])
        self.assertIsNotNone(load_revision(self.revisions, revision))

    def test_directional_rule_rejected_despite_shared_endpoints(self):
        roads = (*self.roads, Road('b_rev', 'K', 'J', 2))
        revision = self.save(roads=roads)
        with self.assertRaisesRegex(ValueError, 'continuous directed'):
            self.save(roads=roads, rules=(Restriction('reverse-middle', ('a', 'b_rev', 'c')),))
        self.assertEqual(self.revision_ids(), [revision])
        self.assertEqual(load_revision(self.revisions, revision).restrictions, self.rules)
        plan = replace(self.single, fragments=(*self.single.fragments, Fragment('r', 'b_rev', 'sheet', 0, 'K', 'J', 2)))
        bundle_id, wire = self.publish(revision, plan)
        self.assertEqual(self.published.find_published(bundle_id), wire)

    def test_invalid_layout_has_no_bundle(self):
        revision = self.save()
        old_id, old_wire = self.publish(revision, self.single)
        incomplete = replace(self.split, fragments=tuple(part for part in self.split.fragments if part.id != 'b2'))
        with self.assertRaises(ValueError):
            self.publish(revision, incomplete)
        self.assertEqual(self.bundle_ids(self.source, 'published'), [old_id])
        self.assertEqual(self.published.find_published(old_id), old_wire)

    def test_broken_chain_rejected_even_with_correct_costs(self):
        revision = self.save()
        broken = replace(self.split, fragments=tuple(
            replace(part, start='J') if part.id == 'b2' else part for part in self.split.fragments
        ))
        with self.assertRaisesRegex(ValueError, 'requires an artificial seam'):
            self.publish(revision, broken)
        self.assertEqual(self.bundle_ids(self.source, 'published'), [])

    def test_per_road_cost_errors_do_not_cancel(self):
        revision = self.save()
        fragments = tuple(replace(part, cost=2) if part.id == 'a' else
                          replace(part, cost=1) if part.id == 'b' else part for part in self.single.fragments)
        self.assertEqual(sum(part.cost for part in fragments), 6)
        with self.assertRaisesRegex(ValueError, 'fragment cost differs'):
            self.publish(revision, replace(self.single, fragments=fragments))
        self.assertEqual(self.bundle_ids(self.source, 'published'), [])

    def test_failed_publish_commit_rolls_back_the_written_bundle(self):
        revision = self.save()
        old_id, old_wire = self.publish(revision, self.single)
        reject_next_commit(self.source, 'fixed_bundles', "NEW.stage = 'published'")
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY'):
            self.publish(revision, self.split)
        self.assertEqual(self.bundle_ids(self.source, 'published'), [old_id])
        self.assertEqual(BundleCatalog(self.source).find_published(old_id), old_wire)
