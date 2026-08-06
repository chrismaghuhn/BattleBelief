from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs/migrations/engine-capability-v1-to-v2.md"


def test_migration_guide_requires_a_v1_capability_catalog() -> None:
    guide = GUIDE.read_text(encoding="utf-8")

    assert "valid v1 capability catalog" in guide
    assert "valid v2 catalog" not in guide
