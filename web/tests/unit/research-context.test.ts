/**
 * Shared research context → study specs. The specs produced from the default context and from a
 * stress context are written to backend/tests/fixtures/context_specs.json (file snapshot); the backend
 * test test_context_specs.py validates every one against the strict (extra="forbid") Pydantic models,
 * so a front-end field the backend does not accept fails CI on both sides.
 */
import { describe, expect, it } from "vitest";
import { DEFAULTS, type ResearchContext } from "@/lib/store";
import { studySpecFromContext } from "@/lib/research/context";
import type { StudyKind } from "@/lib/api/v2";

const KINDS: StudyKind[] = ["frontier", "signed_flow", "permanent", "rebalance", "scenario_lab", "asof", "optimize", "compare_v2", "evidence", "multi_asset", "historical_replay"];
const base = { ...DEFAULTS } as ResearchContext;
const stress: ResearchContext = { ...base, universe: "pp_modern_etf", generator: "student_t", nPaths: 500, gamma: 8, withdrawalRate: 0.06,
  horizonYears: 35, costBps: 10, asOf: "2008-09-30", comparePolicies: "sixty_forty,pp_ex_gold", compareFocus: "pp_ex_gold", retirementAge: 60 };

describe("studySpecFromContext", () => {
  it("maps every study kind and reports universe fallbacks", () => {
    for (const k of KINDS) {
      const { spec, notes } = studySpecFromContext(k, stress);
      expect(spec, k).toBeTypeOf("object");
      if (["frontier", "signed_flow", "rebalance", "scenario_lab", "asof", "optimize", "compare_v2", "multi_asset"].includes(k)) {
        expect(notes.join(" "), k).toMatch(/not usable by this study/);
      }
    }
  });

  it("carries the context values that the study uses", () => {
    expect(studySpecFromContext("permanent", stress).spec.withdrawal).toBe(0.06);
    expect(studySpecFromContext("rebalance", stress).spec.main_cost_bps).toBe(10);
    expect(studySpecFromContext("asof", stress).spec.as_of).toBe("2008-09-30");
    expect(studySpecFromContext("asof", stress).spec.scenario.generator).toBe("markov_switching");
    expect(studySpecFromContext("compare_v2", stress).spec.policies).toEqual(["sixty_forty", "pp_ex_gold"]);
    expect(studySpecFromContext("frontier", base).spec.investor.horizon_years).toBeGreaterThanOrEqual(40);
  });

  it("is deterministic and serialisable (snapshot validated by the backend)", async () => {
    const out = Object.fromEntries(KINDS.flatMap((k) => [[k + ":default", studySpecFromContext(k, base).spec], [k + ":stress", studySpecFromContext(k, stress).spec]]));
    expect(JSON.parse(JSON.stringify(out))).toEqual(out);
    await expect(JSON.stringify(out, null, 2) + "\n").toMatchFileSnapshot("../../../backend/tests/fixtures/context_specs.json");
  });
});
