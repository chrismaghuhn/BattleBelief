from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_base_import_and_status_do_not_touch_optional_engine() -> None:
    runtime_source = Path(__file__).resolve().parents[3] / "src"
    script = """
import importlib.abc
import importlib.metadata
import sys

class RejectEngine(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "poke_engine" or fullname.startswith("poke_engine."):
            raise AssertionError("base import attempted native engine import")
        return None

def reject_distribution(*args, **kwargs):
    raise AssertionError("base status attempted distribution lookup")

sys.meta_path.insert(0, RejectEngine())
importlib.metadata.distribution = reject_distribution
import battlebelief_runtime
from battlebelief_runtime.public_api import runtime_status
assert runtime_status()["phase"] == "M1"
assert "poke_engine" not in sys.modules
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(runtime_source)

    completed = subprocess.run(
        (sys.executable, "-c", script),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
