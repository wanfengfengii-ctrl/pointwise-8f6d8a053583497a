from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from survey.junctions import require_name


@dataclass(frozen=True, slots=True)
class BundleManifest:
    bundle_id: str
    revision_id: int
    layout_id: str
    sha256: str
    version: int = 1


def canonical_json(document) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field {key!r}')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'invalid JSON constant {value!r}')


def read_json(data: bytes):
    if not isinstance(data, bytes):
        raise ValueError('exchange input must be bytes')
    try:
        return json.loads(data, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError('invalid exchange JSON') from error


def _identity_fields(revision_id: int, layout_id: str) -> dict:
    if type(revision_id) is not int or revision_id <= 0:
        raise ValueError('manifest revision id must be a positive integer')
    return {'version': 1, 'revision_id': revision_id, 'layout_id': require_name(layout_id, 'layout id')}


def _digest(fields: dict, payload: bytes) -> str:
    return sha256(canonical_json(fields) + b'\n' + payload).hexdigest()


def build_manifest(
    revision_id: int, layout_id: str, payload: bytes, *, bundle_id: str | None = None
) -> BundleManifest:
    fields = _identity_fields(revision_id, layout_id)
    if bundle_id is None:
        bundle_id = 'pkg-' + _digest(fields, payload)
    else:
        require_name(bundle_id, 'bundle id')
    checksum = _digest({**fields, 'bundle_id': bundle_id}, payload)
    return BundleManifest(bundle_id, revision_id, layout_id, checksum)


def verify_manifest(manifest: BundleManifest, payload: bytes) -> None:
    if type(manifest.version) is not int or manifest.version != 1:
        raise ValueError('unsupported bundle version')
    expected = build_manifest(manifest.revision_id, manifest.layout_id, payload, bundle_id=manifest.bundle_id)
    if manifest != expected:
        raise ValueError('bundle manifest does not match the supplied payload')


def pack_bundle(manifest: BundleManifest, payload: bytes) -> bytes:
    document = read_json(payload)
    canonical_payload = canonical_json(document)
    verify_manifest(manifest, canonical_payload)
    return canonical_json({'manifest': asdict(manifest), 'payload': document})


def unpack_bundle(wire: bytes) -> tuple[BundleManifest, bytes]:
    document = read_json(wire)
    if not isinstance(document, dict) or document.keys() != {'manifest', 'payload'}:
        raise ValueError('expected a bundle envelope with manifest and payload')
    fields = document['manifest']
    if not isinstance(fields, dict) or fields.keys() != {'version', 'bundle_id', 'revision_id', 'layout_id', 'sha256'}:
        raise ValueError('invalid bundle manifest fields')
    manifest = BundleManifest(**fields)
    payload = canonical_json(document['payload'])
    verify_manifest(manifest, payload)
    return manifest, payload
