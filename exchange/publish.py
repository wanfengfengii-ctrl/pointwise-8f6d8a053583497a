from exchange.catalog import BundleCatalog
from exchange.manifest import build_manifest
from exchange.payload import BundlePayload, encode_payload
from survey.revision_store import RevisionStore
from survey.revisions import load_revision
from tiles.layout import LayoutPlan, prepare_layout


def publish(
    revisions: RevisionStore, catalog: BundleCatalog, revision_id: int, plan: LayoutPlan
) -> tuple[str, bytes]:
    revision = load_revision(revisions, revision_id)
    layout = prepare_layout(revision, plan)
    payload = BundlePayload(revision.junctions, revision.roads, layout.tiles, layout.seams, layout.chains, layout.rules)
    encoded = encode_payload(payload)
    manifest = build_manifest(revision.id, layout.id, encoded)
    wire = catalog.commit_publication(manifest, encoded)
    return manifest.bundle_id, wire
