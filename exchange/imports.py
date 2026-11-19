from exchange.catalog import BundleCatalog
from exchange.manifest import unpack_bundle
from exchange.payload import decode_payload
from survey.junctions import index_junctions
from survey.roads import index_roads
from tiles.costs import verify_chain_costs
from tiles.evidence import validate_rule_evidence
from tiles.fragments import validate_fragment_chains
from tiles.layout import validate_tiles
from tiles.seams import index_seams


def import_bundle(catalog: BundleCatalog, wire: bytes) -> str:
    manifest, encoded = unpack_bundle(wire)
    payload = decode_payload(encoded)
    junctions = index_junctions(payload.junctions)
    roads = index_roads(payload.roads, junctions)
    tiles = validate_tiles(payload.tiles)
    seams = index_seams(payload.seams, roads)
    validate_fragment_chains(roads, set(tiles), seams, payload.chains)
    verify_chain_costs(roads, payload.chains)
    validate_rule_evidence(payload.rules, roads, payload.chains)
    return catalog.commit_import(manifest, encoded)
