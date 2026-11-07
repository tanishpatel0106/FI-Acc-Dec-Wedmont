"""Registry of v2 study job kinds: spec model, runner, optional path-trace function and page mapping."""
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel


def _load() -> dict[str, dict[str, Any]]:
    from lifecycle.studies import (
        asof,
        compare_v2,
        evidence,
        frontier,
        optimize_v2,
        permanent,
        rebalance,
        scenario_lab,
        signed_flow,
    )

    return {
        "frontier": {"spec": frontier.FrontierSpec, "run": frontier.run_frontier, "page": "/withdrawal-lab",
                     "experiments": "E01-E03", "figure": "F1"},
        "signed_flow": {"spec": signed_flow.SignedFlowSpec, "run": signed_flow.run_signed_flow,
                        "page": "/lifecycle-flows", "experiments": "E04-E05", "figure": "F2"},
        "permanent": {"spec": permanent.PermanentSpec, "run": permanent.run_permanent, "page": "/permanent-portfolio",
                      "experiments": "E13-E18", "figure": "F3"},
        "rebalance": {"spec": rebalance.RebalanceSpec, "run": rebalance.run_rebalance, "page": "/rebalance",
                      "experiments": "E19-E22", "figure": "F4"},
        "scenario_lab": {"spec": scenario_lab.ScenarioLabSpec, "run": scenario_lab.run_scenario_lab,
                         "page": "/scenarios", "experiments": "E23-E26", "figure": "F5"},
        "asof": {"spec": asof.AsOfSpec, "run": asof.run_asof, "page": "/market-state", "experiments": "E29",
                 "figure": None},
        "optimize": {"spec": optimize_v2.OptimizeSpec, "run": optimize_v2.run_optimize, "page": "/optimize",
                     "experiments": "E07, E30, E33-E34", "figure": None},
        "compare_v2": {"spec": compare_v2.CompareV2Spec, "run": compare_v2.run_compare_v2, "page": "/compare",
                       "experiments": "E24, E26, E36", "figure": "F6"},
        "evidence": {"spec": evidence.EvidenceSpec, "run": evidence.run_evidence, "page": "/research",
                     "experiments": "E28, H1-H12", "figure": "F6"},
    }


_CACHE: dict[str, dict[str, Any]] | None = None


def studies() -> dict[str, dict[str, Any]]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load()
    return _CACHE


def is_study(kind: str) -> bool:
    return kind in studies()


def spec_model(kind: str) -> type[BaseModel]:
    return studies()[kind]["spec"]


def runner(kind: str) -> Callable[..., dict[str, Any]]:
    fn = studies()[kind]["run"]
    return lambda spec, prog, rid: fn(spec, prog)
