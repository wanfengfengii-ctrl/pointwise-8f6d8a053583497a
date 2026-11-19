from survey.junctions import Junction
from survey.restrictions import Restriction
from survey.roads import Road
from tests.support import WorksiteTest, read_payload
from tiles.fragments import Fragment
from tiles.layout import LayoutPlan
from tiles.seams import Seam, SeamKey


class RestrictionRoutingTests(WorksiteTest):
    def _revisit_network(self):
        junctions = tuple(Junction(name) for name in ('X', 'J', 'K', 'T'))
        roads = (
            Road('a', 'X', 'J', 1),
            Road('b', 'J', 'K', 2),
            Road('c', 'K', 'T', 1),
            Road('e', 'K', 'J', 1),
        )
        rules = (Restriction('centre', ('a', 'b', 'c')),)
        single = LayoutPlan('revisit-single', ('sheet',), (), (
            Fragment('a', 'a', 'sheet', 0, 'X', 'J', 1),
            Fragment('b', 'b', 'sheet', 0, 'J', 'K', 2),
            Fragment('c', 'c', 'sheet', 0, 'K', 'T', 1),
            Fragment('e', 'e', 'sheet', 0, 'K', 'J', 1),
        ))
        seam = Seam(SeamKey('b', 'join'), 4, 2)
        split = LayoutPlan('revisit-split', ('west', 'east'), (seam,), (
            Fragment('a', 'a', 'west', 0, 'X', 'J', 1),
            Fragment('b1', 'b', 'west', 0, 'J', SeamKey('b', 'join'), 1),
            Fragment('b2', 'b', 'east', 1, SeamKey('b', 'join'), 'K', 1),
            Fragment('c', 'c', 'east', 0, 'K', 'T', 1),
            Fragment('e', 'e', 'east', 0, 'K', 'J', 1),
        ))
        return junctions, roads, rules, single, split

    def test_history_at_shared_junction_controls_passage_and_revisits_are_legal(self):
        # The first arrival at K (history a,b) cannot take c, while the second
        # arrival after K->J->K (history a,b,e,b) can. The only legal route
        # revisits junction J and road b, and must be found despite that.
        junctions, roads, rules, single, split = self._revisit_network()
        revision = self.save(junctions=junctions, roads=roads, rules=rules)
        expected_route = ('a', 'b', 'e', 'b', 'c')
        expected_cost = 7
        for plan in (single, split):
            with self.subTest(layout=plan.id):
                bundle_id, wire = self.publish(revision, plan)
                record = self.issue(self.accept((bundle_id, wire)))
                self.assert_itinerary(record, expected_cost, expected_route)

    def test_cross_tile_rule_keeps_named_rule_and_ordered_fragment_provenance(self):
        junctions, roads, rules, _, split = self._revisit_network()
        revision = self.save(junctions=junctions, roads=roads, rules=rules)
        bundle_id, wire = self.publish(revision, split)
        self.source.unlink()
        accepted_id = self.accept((bundle_id, wire))
        _, payload = read_payload(self.accepted.find_accepted(accepted_id))
        self.assertEqual(len(payload.rules), 1)
        rule, = payload.rules
        self.assertEqual((rule.id, rule.roads), ('centre', ('a', 'b', 'c')))
        self.assertEqual(
            rule.fragment_refs,
            ((('west', 'a'),), (('west', 'b1'), ('east', 'b2')), (('east', 'c'),)),
        )
        self.assert_itinerary(self.issue(accepted_id), 7, ('a', 'b', 'e', 'b', 'c'))

    def test_blocked_passage_without_alternative_is_unreachable(self):
        junctions = tuple(Junction(name) for name in ('X', 'J', 'K', 'T'))
        roads = (
            Road('a', 'X', 'J', 1),
            Road('b', 'J', 'K', 2),
            Road('c', 'K', 'T', 1),
        )
        rules = (Restriction('centre', ('a', 'b', 'c')),)
        plan = LayoutPlan('dead-single', ('sheet',), (), (
            Fragment('a', 'a', 'sheet', 0, 'X', 'J', 1),
            Fragment('b', 'b', 'sheet', 0, 'J', 'K', 2),
            Fragment('c', 'c', 'sheet', 0, 'K', 'T', 1),
        ))
        revision = self.save(junctions=junctions, roads=roads, rules=rules)
        record = self.issue(self.accept(self.publish(revision, plan)))
        self.assert_itinerary(record, None, None)
        self.assertFalse(record.itinerary.reachable)

    def test_restriction_judged_on_original_roads_not_fragments(self):
        # With the rule lifted, the direct triple is the shortest route even
        # though the middle original road is assembled from two fragments.
        junctions, roads, _, _, split = self._revisit_network()
        revision = self.save(junctions=junctions, roads=roads, rules=())
        record = self.issue(self.accept(self.publish(revision, split)))
        self.assert_itinerary(record, 4, ('a', 'b', 'c'))
