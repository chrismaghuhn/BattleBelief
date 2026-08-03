from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from battlebelief_lab.registration_validation import (  # noqa: E402
    validate_repository_artifacts,
)


def main() -> int:
    errors = validate_repository_artifacts(ROOT)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("PASS: M1.5 registration artifacts and semantic references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
