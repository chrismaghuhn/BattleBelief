from __future__ import annotations

from typing import TYPE_CHECKING

from battlebelief_core.domain.search import SearchAction
from battlebelief_core.ports.transition_model import TransitionModel
from battlebelief_runtime.adapters.poke_engine import PokeEngineTransitionModel
from battlebelief_runtime.adapters.poke_engine.transition_model import _PokeEngineWorld

if TYPE_CHECKING:
    _PORT_CONFORMANCE: TransitionModel[_PokeEngineWorld, SearchAction] = (
        PokeEngineTransitionModel.__new__(PokeEngineTransitionModel)
    )


def test_real_adapter_exposes_the_runtime_checkable_transition_protocol() -> None:
    assert isinstance(PokeEngineTransitionModel.__new__(PokeEngineTransitionModel), TransitionModel)


def test_public_adapter_surface_contains_only_approved_types_and_sentinel() -> None:
    import battlebelief_runtime.adapters.poke_engine as adapter

    assert adapter.__all__ == [
        "MappingReport",
        "PokeEngineMappingFailure",
        "PokeEngineTransitionModel",
        "RequiredCapabilities",
        "run_gen9_sentinel",
    ]
    assert "State" not in vars(adapter)
    assert "legal_choices" not in vars(adapter)
