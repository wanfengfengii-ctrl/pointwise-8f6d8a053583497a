from exchange.manifest import BundleManifest, pack_bundle
from storage import DatabasePath, connect, write_transaction
from survey.junctions import require_name


class BundleCatalog:
    def __init__(self, path: DatabasePath):
        self.path = path

    def initialize(self) -> None:
        with connect(self.path) as database, write_transaction(database):
            database.execute('''
                CREATE TABLE IF NOT EXISTS fixed_bundles (
                    stage TEXT NOT NULL CHECK (stage IN ('published', 'accepted')),
                    bundle_id TEXT NOT NULL,
                    wire BLOB NOT NULL,
                    PRIMARY KEY (stage, bundle_id)
                )
            ''')

    def _commit(self, stage: str, manifest: BundleManifest, payload: bytes) -> bytes:
        wire = pack_bundle(manifest, payload)
        key = stage, manifest.bundle_id
        with connect(self.path) as database, write_transaction(database):
            row = database.execute(
                'SELECT wire FROM fixed_bundles WHERE stage = ? AND bundle_id = ?', key
            ).fetchone()
            if row is None:
                database.execute('INSERT INTO fixed_bundles(stage, bundle_id, wire) VALUES (?, ?, ?)', (*key, wire))
            elif row[0] != wire:
                raise ValueError(f'bundle id {manifest.bundle_id!r} already identifies another fixed bundle')
        return wire

    def commit_publication(self, manifest: BundleManifest, payload: bytes) -> bytes:
        return self._commit('published', manifest, payload)

    def commit_import(self, manifest: BundleManifest, payload: bytes) -> str:
        self._commit('accepted', manifest, payload)
        return manifest.bundle_id

    def _find(self, stage: str, bundle_id: str) -> bytes | None:
        require_name(bundle_id, 'bundle id')
        with connect(self.path) as database:
            row = database.execute(
                'SELECT wire FROM fixed_bundles WHERE stage = ? AND bundle_id = ?', (stage, bundle_id)
            ).fetchone()
        return None if row is None else row[0]

    def find_published(self, bundle_id: str) -> bytes | None:
        return self._find('published', bundle_id)

    def find_accepted(self, bundle_id: str) -> bytes | None:
        return self._find('accepted', bundle_id)
