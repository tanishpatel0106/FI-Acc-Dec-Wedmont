"use client";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Field, NativeSelect, NumberInput } from "@/components/common/Fields";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { useBuilder, DEFAULTS } from "@/lib/store";
import { pct } from "@/lib/format";

// mirrors the ExperimentSpec bounds in backend/lifecycle/runs/spec.py (OpenAPI)
export const investorSchema = z
  .object({
    startAge: z.number().min(20).max(95),
    retirementAge: z.number().min(40).max(80),
    maxAge: z.number().min(70).max(110),
    wealth: z.number().min(0),
    income: z.number().min(0),
    savingsRate: z.number().min(0).max(0.8),
    pension: z.number().min(0),
    gamma: z.number().min(0.5).max(15),
    beta: z.number().gt(0.5).max(1),
    eta: z.number().min(0),
    cMin: z.number().gt(0),
    withdrawalRate: z.number().min(0).max(0.2),
    nPaths: z.number().int().min(100).max(100000),
    costBps: z.number().min(0).max(200),
    rebalanceMonths: z.number().int().min(1).max(60),
  })
  .refine((v) => v.maxAge > v.startAge + 1, { message: "max age must exceed start age", path: ["maxAge"] });

type FormValues = z.infer<typeof investorSchema>;

export const POLICY_OPTIONS = [
  { value: "sixty_forty", label: "60/40 constant mix" },
  { value: "target_date", label: "Target-date glidepath" },
  { value: "best_constant", label: "Best constant mix (fitted)" },
  { value: "glidepath", label: "Linear glidepath (fitted)" },
  { value: "risk_parity", label: "Risk parity" },
  { value: "min_variance", label: "Minimum variance" },
  { value: "mean_variance", label: "Mean–variance (λ = γ)" },
  { value: "mean_cvar", label: "Mean–CVaR (LP)" },
  { value: "utility_static", label: "Static CRRA-optimal mix" },
  { value: "regime", label: "Regime-dependent mix" },
  { value: "bucket", label: "Liability-matched bucket" },
  { value: "parametric", label: "Parametric dynamic policy" },
  { value: "dp", label: "Grid DP (reduced 3-asset)" },
];

export function InvestorForm() {
  const s = useBuilder();
  const form = useForm<FormValues>({ resolver: zodResolver(investorSchema), mode: "onChange", defaultValues: {
    startAge: s.startAge, retirementAge: s.retirementAge, maxAge: s.maxAge, wealth: s.wealth, income: s.income,
    savingsRate: s.savingsRate, pension: s.pension, gamma: s.gamma, beta: s.beta, eta: s.eta, cMin: s.cMin,
    withdrawalRate: s.withdrawalRate, nPaths: s.nPaths, costBps: s.costBps, rebalanceMonths: s.rebalanceMonths } });
  const errors = form.formState.errors;
  const setStore = s.set;
  useEffect(() => {
    const sub = form.watch((v) => {
      const parsed = investorSchema.safeParse(v);
      if (parsed.success) setStore(parsed.data);
    });
    return () => sub.unsubscribe();
  }, [form, setStore]);
  const num = (name: keyof FormValues, label: string, step: number, hint?: string) => (
    <Field label={label} hint={errors[name]?.message ?? hint}>
      <NumberInput value={form.watch(name) as number} step={step} invalid={!!errors[name]}
        onChange={(v) => form.setValue(name, v as never, { shouldValidate: true })} />
    </Field>
  );
  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Investor</div>
        <div className="grid grid-cols-2 gap-3">
          {num("startAge", "Start age", 1)}
          {num("retirementAge", "Retirement age", 1)}
          {num("maxAge", "Max age", 1)}
          {num("wealth", "Financial wealth ($)", 10000)}
          {num("income", "Labor income ($/yr)", 5000, "CGM college profile")}
          {num("pension", "Pension ($/yr, real)", 1000, "Social Security proxy")}
        </div>
        <Field label={"Savings rate " + pct(s.savingsRate, 0)} className="mt-3">
          <Slider value={[s.savingsRate * 100]} min={0} max={40} step={1} onValueChange={(v) => form.setValue("savingsRate", (Array.isArray(v) ? v[0] : v) / 100, { shouldValidate: true })} />
        </Field>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <Field label="Sex (life table)">
            <NativeSelect value={s.sex} onChange={(v) => s.set({ sex: v })} options={[{ value: "unisex", label: "Unisex" }, { value: "female", label: "Female" }, { value: "male", label: "Male" }]} />
          </Field>
          <Field label="Mortality (SSA)">
            <div className="flex h-8 items-center"><Switch checked={s.mortality} onCheckedChange={(v) => s.set({ mortality: v })} /></div>
          </Field>
        </div>
      </div>
      <div>
        <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Preferences</div>
        <div className="grid grid-cols-2 gap-3">
          {num("gamma", "Risk aversion γ", 0.5)}
          {num("beta", "Discount β (annual)", 0.005)}
          {num("eta", "Bequest weight η", 0.5)}
          {num("cMin", "Consumption floor ($/yr)", 1000)}
        </div>
      </div>
      <div>
        <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Policy & spending</div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Allocation policy" className="col-span-2">
            <NativeSelect value={s.policy} onChange={(v) => s.set({ policy: v })} options={POLICY_OPTIONS} />
          </Field>
          <Field label="Spending rule">
            <NativeSelect value={s.spendingRule} onChange={(v) => s.set({ spendingRule: v })} options={[
              { value: "fixed_real", label: "Fixed real" }, { value: "fixed_pct", label: "Fixed percentage" },
              { value: "guardrails", label: "Guardrails (G–K)" }, { value: "utility_optimal", label: "Utility-optimal (amortised)" }]} />
          </Field>
          <Field label={"Withdrawal rate " + pct(s.withdrawalRate, 1)}>
            <Slider value={[s.withdrawalRate * 1000]} min={20} max={80} step={5} onValueChange={(v) => form.setValue("withdrawalRate", (Array.isArray(v) ? v[0] : v) / 1000, { shouldValidate: true })} />
          </Field>
          {num("rebalanceMonths", "Rebalance every (months)", 1)}
          {num("costBps", "Cost κ (bp, one-way)", 1)}
          <Field label="Benchmark">
            <NativeSelect value={s.benchmark} onChange={(v) => s.set({ benchmark: v })} options={[
              { value: "sixty_forty", label: "60/40" }, { value: "target_date", label: "Target-date" },
              { value: "best_constant", label: "Best constant mix" }, { value: "none", label: "None" }]} />
          </Field>
        </div>
      </div>
      <div>
        <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Scenarios</div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Universe">
            <NativeSelect value={s.universe} onChange={(v) => s.set({ universe: v })} options={[{ value: "core", label: "Long-history core" }, { value: "modern", label: "Modern diversified" }]} />
          </Field>
          <Field label="Generator">
            <NativeSelect value={s.generator} onChange={(v) => s.set({ generator: v })} options={[
              { value: "bootstrap", label: "Block bootstrap" }, { value: "student_t", label: "Student-t" },
              { value: "markov_switching", label: "Markov switching" }, { value: "historical", label: "Historical cohorts" },
              { value: "curve_factor", label: "Yield-curve factors" }]} />
          </Field>
          {num("nPaths", "Paths", 500)}
          <Field label="Seed"><NumberInput value={s.seed} onChange={(v) => s.set({ seed: Number.isFinite(v) ? Math.round(v) : DEFAULTS.seed })} /></Field>
        </div>
      </div>
    </div>
  );
}
