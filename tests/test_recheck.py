from exchange.catalog import BundleCatalog
from review.compare import compare
from review.record_store import RecordStore
from review.retrieve import retrieve
from survey.revision_store import RevisionStore
from survey.revisions import load_revision
from tests.support import WorksiteTest


class RecheckTests(WorksiteTest):
    def test_old_record_after_revision_and_reopen(self):
        before = self.save()
        before_bundle = self.publish(before, self.split)
        old = self.issue(self.accept(before_bundle))
        after = self.save(rules=())
        after_bundle = self.publish(after, self.split)
        new = self.issue(self.accept(after_bundle))
        self.assertNotEqual(before_bundle[0], after_bundle[0])
        source_reopened = BundleCatalog(self.source)
        self.assertEqual(source_reopened.find_published(before_bundle[0]), before_bundle[1])
        self.assertEqual(source_reopened.find_published(after_bundle[0]), after_bundle[1])
        self.source.unlink()
        catalog = BundleCatalog(self.offline)
        records = RecordStore(self.offline)
        self.assertEqual(catalog.find_accepted(before_bundle[0]), before_bundle[1])
        self.assertEqual(catalog.find_accepted(after_bundle[0]), after_bundle[1])
        previous = retrieve(records, old.id)
        current = retrieve(records, new.id)
        self.assertEqual((previous, current), (old, new))
        self.assert_itinerary(previous, 5, ('h', 'd', 'b', 'c'))
        self.assert_itinerary(current, 4, ('a', 'b', 'c'))
        result = compare(records, old.id, new.id)
        self.assertEqual((result.before.request.bundle_id, result.after.request.bundle_id), (before_bundle[0], after_bundle[0]))
        self.assertEqual((result.reachability_changed, result.route_changed, result.cost_changed), (False, True, True))

    def test_same_cost_route_change(self):
        roads, (_, split) = self.adjusted_a(2)
        old_id = self.accept(self.publish(self.save(roads=roads), split))
        old = self.issue(old_id)
        new_id = self.accept(self.publish(self.save(roads=roads, rules=()), split))
        new = self.issue(new_id)
        self.source.unlink()
        records = RecordStore(self.offline)
        previous = retrieve(records, old.id)
        current = retrieve(records, new.id)
        self.assertEqual((previous, current), (old, new))
        self.assert_itinerary(previous, 5, ('h', 'd', 'b', 'c'))
        self.assert_itinerary(current, 5, ('a', 'b', 'c'))
        result = compare(records, old.id, new.id)
        self.assertEqual((result.before, result.after), (old, new))
        self.assertEqual((result.before.request.bundle_id, result.after.request.bundle_id), (old_id, new_id))
        self.assertTrue(result.route_changed)
        self.assertFalse(result.cost_changed)
        self.assertFalse(result.reachability_changed)

    def test_initialization_preserves_user_edits(self):
        for store in (self.revisions, self.published, self.accepted, self.records):
            store.initialize()
            store.initialize()
        self.assertEqual(self.revision_ids(), [])
        self.assertEqual(self.bundle_ids(self.source, 'published'), [])
        self.assertEqual(self.bundle_ids(self.offline, 'accepted'), [])
        self.assertEqual(self.record_ids(), [])
        before = self.save()
        before_bundle = self.publish(before, self.split)
        before_record = self.issue(self.accept(before_bundle))
        after = self.save(rules=())
        after_bundle = self.publish(after, self.single)
        after_record = self.issue(self.accept(after_bundle))
        source, published = RevisionStore(self.source), BundleCatalog(self.source)
        accepted, records = BundleCatalog(self.offline), RecordStore(self.offline)
        for store in (source, published, accepted, records):
            store.initialize()
            store.initialize()
        self.assertEqual(self.revision_ids(), [before, after])
        self.assertEqual(load_revision(source, before).restrictions, self.rules)
        self.assertEqual(load_revision(source, after).restrictions, ())
        for bundle_id, wire in (before_bundle, after_bundle):
            self.assertEqual(published.find_published(bundle_id), wire)
            self.assertEqual(accepted.find_accepted(bundle_id), wire)
        self.assertEqual((retrieve(records, before_record.id), retrieve(records, after_record.id)), (before_record, after_record))

    def test_compare_invalid_pair(self):
        bundle_id = self.accept(self.publish(self.save(), self.split))
        first = self.issue(bundle_id)
        reverse = self.issue(bundle_id, 'T', 'X')
        absent = reverse.id + 1
        records = RecordStore(self.offline)
        self.assertIsNone(retrieve(records, absent))
        with self.assertRaises(KeyError):
            compare(records, first.id, absent)
        with self.assertRaises(KeyError):
            compare(records, absent, first.id)
        with self.assertRaisesRegex(ValueError, 'same ordered endpoint pair'):
            compare(records, first.id, reverse.id)
        self.assertEqual(retrieve(records, first.id), first)
        self.assertEqual(retrieve(records, reverse.id), reverse)
        self.assertEqual(self.record_ids(), [first.id, reverse.id])
