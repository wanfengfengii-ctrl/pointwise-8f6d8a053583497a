import json
from pathlib import Path
from tempfile import TemporaryDirectory

from exchange.catalog import BundleCatalog
from exchange.imports import import_bundle
from exchange.publish import publish
from review.compare import compare
from review.issue import issue
from review.record_store import RecordStore
from review.requests import ReviewRequest
from review.retrieve import retrieve
from survey.junctions import Junction
from survey.restrictions import Restriction
from survey.revision_store import RevisionStore
from survey.revisions import save_revision
from survey.roads import Road
from tiles.fragments import Fragment
from tiles.layout import LayoutPlan
from tiles.seams import Seam, SeamKey


SAMPLES = Path(__file__).resolve().parent / 'samples'


def _endpoint(value):
    return SeamKey(*value) if isinstance(value, list) else value


def load_sample():
    survey = json.loads((SAMPLES / 'network.json').read_text(encoding='utf-8'))
    layouts = json.loads((SAMPLES / 'layouts.json').read_text(encoding='utf-8'))
    plans = {}
    for name, layout in layouts.items():
        seams = tuple(Seam(SeamKey(road, label), x, y) for road, label, x, y in layout['seams'])
        fragments = tuple(
            Fragment(label, road, tile, ordinal, _endpoint(start), _endpoint(end), cost)
            for label, road, tile, ordinal, start, end, cost in layout['fragments']
        )
        plans[name] = LayoutPlan(name, tuple(layout['tiles']), seams, fragments)
    return (
        tuple(Junction(name) for name in survey['junctions']),
        tuple(Road(*road) for road in survey['roads']),
        tuple(Restriction(name, tuple(roads)) for name, roads in survey['restrictions']),
        plans,
    )


def _result(record):
    roads = record.itinerary.roads
    return {"cost": record.itinerary.cost, "roads": None if roads is None else list(roads)}


def main():
    with TemporaryDirectory(prefix='chengwan-demo-') as directory:
        source = Path(directory) / 'survey.sqlite3'
        offline = Path(directory) / 'review.sqlite3'
        revisions, published = RevisionStore(source), BundleCatalog(source)
        accepted, records = BundleCatalog(offline), RecordStore(offline)
        for store in (revisions, published, accepted, records):
            store.initialize()
        junctions, roads, rules, plans = load_sample()
        before = save_revision(revisions, junctions, roads, rules)
        single_id, single_wire = publish(revisions, published, before, plans['single'])
        before_id, before_wire = publish(revisions, published, before, plans['split'])
        after = save_revision(revisions, junctions, roads, ())
        after_id, after_wire = publish(revisions, published, after, plans['split'])
        source.unlink()

        issued = []
        for bundle_id, wire in ((single_id, single_wire), (before_id, before_wire), (after_id, after_wire)):
            if import_bundle(accepted, wire) != bundle_id:
                raise AssertionError('accepted the wrong package')
            issued.append(issue(accepted, records, ReviewRequest(bundle_id, 'X', 'T')))

        reopened = RecordStore(offline)
        previous = retrieve(reopened, issued[1].id)
        current = retrieve(reopened, issued[2].id)
        comparison = compare(reopened, previous.id, current.id)
        expected = {
            'single': {'cost': 5, 'roads': ['h', 'd', 'b', 'c']},
            'split': {'cost': 5, 'roads': ['h', 'd', 'b', 'c']},
            'correction': {'cost': 4, 'roads': ['a', 'b', 'c']},
        }
        actual = {'single': _result(issued[0]), 'split': _result(previous), 'correction': _result(current)}
        downstream_expected = {'old_bundle': before_id, 'new_bundle': after_id, 'route_changed': True, 'cost_changed': True}
        downstream_actual = {
            'old_bundle': comparison.before.request.bundle_id,
            'new_bundle': comparison.after.request.bundle_id,
            'route_changed': comparison.route_changed,
            'cost_changed': comparison.cost_changed,
        }
        if actual != expected or downstream_actual != downstream_expected or issued[1:] != [previous, current]:
            raise AssertionError(f'route review differs from the hand calculation: {actual!r}, {downstream_actual!r}')
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v7',
            'input': {'roads': [[road.id, road.start, road.end, road.cost] for road in roads],
                      'old_rules': [['a', 'b', 'c']], 'new_rules': [], 'split_road': 'b', 'endpoints': ['X', 'T']},
            'expected': expected,
            'actual': actual,
            'downstream_expected': downstream_expected,
            'downstream_actual': downstream_actual,
            'code_paths': ['exchange/publish.py', 'exchange/imports.py', 'routing/search.py',
                           'review/issue.py', 'review/retrieve.py', 'review/compare.py'],
            'oracle': 'Manually sum the two possible X-to-T routes and discard a-b-c for the original revision.',
        }, sort_keys=True))


if __name__ == '__main__':
    main()
