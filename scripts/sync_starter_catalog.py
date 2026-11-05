"""Copy the generic application patterns from catalog/ into the package's starter catalog.

    python scripts/sync_starter_catalog.py

`pcat init --starter` copies src/pcat/starter/catalog/ into a team's repository, so the
starter must be available without this repository. tests/test_starter.py fails when the
copies drift from catalog/.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pcat import catalog as cat  # noqa: E402
from pcat import starter  # noqa: E402


def main() -> int:
    dest = starter.ROOT / cat.CATALOG_DIR
    if dest.exists():
        shutil.rmtree(dest)
    for pattern_id in starter.PATTERN_IDS:
        src = cat.get_one(ROOT, pattern_id).folder
        target = dest / src.relative_to(ROOT / cat.CATALOG_DIR)
        target.mkdir(parents=True)
        for name in starter.FILES:
            shutil.copy2(src / name, target / name)
    cat.write_index(starter.ROOT)
    print(f"wrote {len(starter.PATTERN_IDS)} patterns to {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
