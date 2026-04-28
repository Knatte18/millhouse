"""Unit tests for plugins/mill/scripts/_builder_lock.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _builder_lock import LOCK_FILENAME, LockBusy, acquire, read, release  # noqa: E402


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            mill = Path(tmp)
            assert read(mill) is None
            print("PASS: read() on empty dir -> None")

            info = acquire(mill, "demo")
            assert info.slug == "demo"
            assert (mill / LOCK_FILENAME).exists()
            print(f"PASS: acquire('demo') -> {info.timestamp}")

            info2 = acquire(mill, "demo")
            assert info2.slug == "demo"
            print("PASS: acquire same slug is idempotent (refresh)")

            try:
                acquire(mill, "other-slug")
            except LockBusy as exc:
                assert "demo" in str(exc)
                print(f"PASS: acquire conflicting slug -> LockBusy ({exc})")
            else:
                raise AssertionError("acquire should have raised LockBusy")

            # Force staleness: overwrite timestamp with one well past the window.
            stale_ts = "2000-01-01T00:00:00Z"
            (mill / LOCK_FILENAME).write_text(
                f"```yaml\nslug: demo\ntimestamp: {stale_ts}\n```\n", encoding="utf-8"
            )
            info3 = acquire(mill, "new-slug")
            assert info3.slug == "new-slug"
            print("PASS: acquire over stale lock succeeds")

            release(mill)
            assert not (mill / LOCK_FILENAME).exists()
            print("PASS: release() removes the lock")

            release(mill)
            print("PASS: release() on absent lock is a no-op")

        # Colon in slug round-trip.
        with tempfile.TemporaryDirectory() as tmp:
            mill = Path(tmp)
            acquire(mill, "injected: colon")
            info_colon = read(mill)
            assert info_colon is not None, "lock should exist after acquire"
            assert info_colon.slug == "injected: colon", (
                f"slug colon round-trip failed: {info_colon.slug!r}"
            )
            print("PASS: acquire quotes slug with colon; read round-trips it")

        print("All _builder_lock unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
