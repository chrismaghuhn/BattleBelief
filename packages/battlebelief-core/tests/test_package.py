from battlebelief_core import __version__


def test_core_version_is_lockstep_version() -> None:
    assert __version__ == "0.2.0"
