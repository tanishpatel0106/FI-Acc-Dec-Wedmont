"""M3 scenario generators. All produce the same ScenarioTensor (paths x months x series)."""
from lifecycle.engine.scenarios.base import CHUNK, ScenarioTensor, generate
from lifecycle.engine.scenarios.registry import GENERATORS, fit_generator

__all__ = ["CHUNK", "ScenarioTensor", "generate", "GENERATORS", "fit_generator"]
