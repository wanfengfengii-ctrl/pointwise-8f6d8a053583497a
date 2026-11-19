from dataclasses import dataclass

from exchange.manifest import canonical_json, read_json
from survey.junctions import Junction, require_name
from survey.roads import Road, decode_cost, encode_cost
from tiles.evidence import RuleEvidence
from tiles.fragments import Fragment, FragmentChain, assemble_fragment_chains
from tiles.seams import Endpoint, Seam, SeamKey


@dataclass(frozen=True, slots=True)
class BundlePayload:
    junctions: tuple[Junction, ...]
    roads: tuple[Road, ...]
    tiles: tuple[str, ...]
    seams: tuple[Seam, ...]
    chains: tuple[FragmentChain, ...]
    rules: tuple[RuleEvidence, ...]


def _encode_endpoint(endpoint: Endpoint) -> list[str]:
    if isinstance(endpoint, SeamKey):
        return ['seam', endpoint.road_id, endpoint.id]
    return ['junction', endpoint]


def _fragment_row(fragment: Fragment) -> list:
    return [
        fragment.id, fragment.road_id, fragment.tile_id, fragment.ordinal,
        _encode_endpoint(fragment.start), _encode_endpoint(fragment.end), encode_cost(fragment.cost),
    ]


def encode_payload(payload: BundlePayload) -> bytes:
    return canonical_json({
        'junctions': [junction.id for junction in payload.junctions],
        'roads': [[road.id, road.start, road.end, encode_cost(road.cost)] for road in payload.roads],
        'tiles': list(payload.tiles),
        'seams': [[seam.key.road_id, seam.key.id, seam.x, seam.y] for seam in payload.seams],
        'fragments': [_fragment_row(fragment) for chain in payload.chains for fragment in chain.fragments],
        'rules': [[rule.id, rule.roads, rule.fragment_refs] for rule in payload.rules],
    })


def _array(value, field: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f'{field} must be a JSON array')
    return value


def _row(value, width: int, field: str) -> list:
    row = _array(value, field)
    if len(row) != width:
        raise ValueError(f'{field} must contain exactly {width} values')
    return row


def _decode_endpoint(value) -> Endpoint:
    row = _array(value, 'endpoint')
    if len(row) == 2 and row[0] == 'junction':
        return require_name(row[1], 'endpoint junction')
    if len(row) == 3 and row[0] == 'seam':
        return SeamKey(require_name(row[1], 'endpoint seam road'), require_name(row[2], 'endpoint seam name'))
    raise ValueError('unknown endpoint encoding')


def _decode_fragment(value) -> Fragment:
    name, road, tile, ordinal, start, end, cost = _row(value, 7, 'fragment')
    return Fragment(name, road, tile, ordinal, _decode_endpoint(start), _decode_endpoint(end), decode_cost(cost))


def _decode_rule(value) -> RuleEvidence:
    name, roads, groups = _row(value, 3, 'rule')
    return RuleEvidence(
        name,
        tuple(_row(roads, 3, 'rule roads')),
        tuple(
            tuple(tuple(_row(ref, 2, 'fragment reference')) for ref in _array(group, 'rule fragment group'))
            for group in _row(groups, 3, 'rule fragment groups')
        ),
    )


def decode_payload(encoded: bytes) -> BundlePayload:
    document = read_json(encoded)
    fields = {'junctions', 'roads', 'tiles', 'seams', 'fragments', 'rules'}
    if not isinstance(document, dict) or document.keys() != fields:
        raise ValueError('invalid bundle payload fields')
    junctions = tuple(Junction(name) for name in _array(document['junctions'], 'junctions'))
    roads = tuple(
        Road(name, start, end, decode_cost(cost))
        for name, start, end, cost in (_row(value, 4, 'road') for value in _array(document['roads'], 'roads'))
    )
    seams = tuple(
        Seam(SeamKey(road, name), x, y)
        for road, name, x, y in (_row(value, 4, 'seam') for value in _array(document['seams'], 'seams'))
    )
    chains = assemble_fragment_chains(_decode_fragment(value) for value in _array(document['fragments'], 'fragments'))
    rules = tuple(_decode_rule(value) for value in _array(document['rules'], 'rules'))
    return BundlePayload(junctions, roads, tuple(_array(document['tiles'], 'tiles')), seams, chains, rules)
