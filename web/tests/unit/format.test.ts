import { describe, expect, it } from "vitest";
import { pct, signedPct, usd, usdK } from "@/lib/format";
import { builderFromQuery, builderToQuery, DEFAULTS, specFromBuilder } from "@/lib/store";

describe("format", () => {
  it("formats percentages and money", () => {
    expect(pct(0.0412)).toBe("4.1%");
    expect(signedPct(0.0123)).toBe("+1.23%");
    expect(signedPct(-0.5, 0)).toBe("-50%");
    expect(usd(58912.4)).toBe("$58,912");
    expect(usdK(1_250_000)).toBe("$1.25M");
    expect(pct(null)).toBe("–");
  });
});

describe("builder <-> URL", () => {
  it("round-trips non-default fields only", () => {
    const state = { ...DEFAULTS, startAge: 55, gamma: 6, policy: "parametric" };
    const q = builderToQuery(state);
    expect(q).toContain("startAge=55");
    expect(q).not.toContain("wealth=");
    const back = builderFromQuery(new URLSearchParams(q));
    expect(back).toEqual({ startAge: 55, gamma: 6, policy: "parametric" });
  });

  it("maps the builder onto an ExperimentSpec", () => {
    const spec = specFromBuilder({ ...DEFAULTS });
    expect(spec.policy.type).toBe("sixty_forty");
    expect(spec.investor.start_age).toBe(65);
    expect(spec.scenario.n_train_paths).toBeLessThanOrEqual(spec.scenario.n_paths);
  });
});
