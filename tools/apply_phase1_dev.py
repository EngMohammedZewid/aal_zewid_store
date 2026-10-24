"""Apply Phase 1 to a development copy of the database.

The repository store.db file is never opened for writing and is never passed to
the migration. A checkpointed database is byte-copied. A database with a WAL or
rollback journal is snapshotted through the SQLite backup API first.
"""

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from core.phase1_foundation import ProductionMigrationBlocked, is_production_database, migrate_database


DEV_DATABASE = Path("dev_data") / "store.phase1.db"


def _temp_snapshot_path():
    temp_handle = tempfile.NamedTemporaryFile(prefix="phase1_snapshot_", suffix=".db", delete=False)
    snapshot_path = Path(temp_handle.name)
    temp_handle.close()
    return snapshot_path


def _remove_sqlite_family(path):
    target = Path(path)
    for candidate in (target, Path(str(target) + "-wal"), Path(str(target) + "-shm")):
        if candidate.exists():
            candidate.unlink()


def _snapshot_database(source_path):
    """Copy a consistent snapshot without writing the source database."""
    source = Path(source_path)
    sidecars = [Path(str(source) + suffix) for suffix in ("-wal", "-shm", "-journal")]
    snapshot_path = _temp_snapshot_path()
    if all(not sidecar.exists() for sidecar in sidecars):
        before = (source.stat().st_mtime_ns, source.stat().st_size)
        shutil.copyfile(source, snapshot_path)
        after = (source.stat().st_mtime_ns, source.stat().st_size)
        if before == after and all(not sidecar.exists() for sidecar in sidecars):
            return snapshot_path
        _remove_sqlite_family(snapshot_path)
        snapshot_path = _temp_snapshot_path()

    source_uri = source.resolve().as_uri() + "?mode=ro"
    source_connection = sqlite3.connect(source_uri, uri=True)
    destination = sqlite3.connect(snapshot_path)
    try:
        source_connection.execute("PRAGMA query_only = ON")
        source_connection.backup(destination)
    finally:
        destination.close()
        source_connection.close()
    return snapshot_path


def create_dev_database(source, destination):
    if is_production_database(destination):
        raise ProductionMigrationBlocked("The development database must not be store.db")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    snapshot = _snapshot_database(source)
    try:
        if destination.exists():
            _remove_sqlite_family(destination)
        shutil.copyfile(snapshot, destination)
    finally:
        _remove_sqlite_family(snapshot)
    return destination


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("store.db")
    destination = create_dev_database(source, DEV_DATABASE)
    migrate_database(destination)
    print(f"Phase 1 applied to {destination.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
