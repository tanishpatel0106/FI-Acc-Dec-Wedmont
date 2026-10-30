"use client";
import Link from "next/link";
import { IconChartAreaLine, IconChartDots3, IconFlask2, IconGitCompare, IconTable } from "@tabler/icons-react";
import { Spotlight } from "@/components/ui/spotlight";
import { TextGenerateEffect } from "@/components/ui/text-generate-effect";
import { BentoGrid, BentoGridItem } from "@/components/ui/bento-grid";
import { GlowingEffect } from "@/components/ui/glowing-effect";
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";
import { useCatalog, useOverview } from "@/lib/api/hooks";
import { BENCHMARK_LABELS, pct, signedPct } from "@/lib/format";

const QUESTION =
  "How should an investor allocate across asset classes as contribution rate, withdrawal rate, horizon, wealth and the economic regime change — and what is that worth in certainty-equivalent consumption?";

function Tile({ href, title, description, icon, header, className }: {
  href: string; title: string; description: React.ReactNode; icon: React.ReactNode; header: React.ReactNode; className?: string;
}) {
  return (
    <Link href={href} className={"relative block rounded-xl " + (className ?? "")}>
      <GlowingEffect spread={36} glow proximity={56} inactiveZone={0.02} borderWidth={2} disabled={false} />
      <BentoGridItem className="h-full border-border bg-card dark:bg-card" title={title} description={description} icon={icon} header={header} />
    </Link>
  );
}

function Kpi({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="flex h-full min-h-24 flex-col justify-center rounded-lg bg-muted/40 px-4">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {sub ? <div className="text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

export function Overview() {
  const ov = useOverview();
  const cat = useCatalog();
  const dec = ov.data?.latest_sweeps?.decumulation;
  const acc = ov.data?.latest_sweeps?.accumulation;
  const core = cat.data?.universes?.core;
  const modern = cat.data?.universes?.modern;
  return (
    <div className="space-y-10">
      <div className="relative overflow-hidden rounded-2xl border border-border bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-neutral-900 via-background to-background px-6 py-14 md:px-12">
        <Spotlight className="-top-40 left-0 md:-top-20 md:left-60" fill="#3987e5" />
        <div className="relative z-10 max-w-4xl">
          <div className="text-xs font-medium uppercase tracking-[0.25em] text-muted-foreground">
            LIFECYCLE · Wedmont Private Capital × Columbia
          </div>
          <TextGenerateEffect words={QUESTION} className="mt-4 text-xl font-medium leading-snug md:text-2xl" duration={0.35} />
          <p className="mt-4 max-w-2xl text-sm text-muted-foreground">
            A cash-flow-aware lifecycle engine: real accounting at monthly frequency, CRRA utility with mortality,
            joint scenario generators, and every comparison run on common random numbers with Monte Carlo,
            parameter and model uncertainty reported separately.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/withdrawal-lab">
              <HoverBorderGradient as="div" containerClassName="rounded-full" className="bg-background px-5 py-2 text-sm text-foreground">
                Open heatmap →
              </HoverBorderGradient>
            </Link>
            <Link href="/simulate" className="rounded-full border border-border px-5 py-2 text-sm text-muted-foreground hover:text-foreground">
              Run an experiment
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Headline ΔCE (best cell)" value={dec ? signedPct(dec.max_delta) : "—"}
          sub={dec ? `vs ${BENCHMARK_LABELS[dec.benchmark] ?? dec.benchmark}, ${dec.universe}, γ=${dec.gamma}` : "run `make seed`"} />
        <Kpi label="Mean ΔCE across cells" value={dec ? signedPct(dec.mean_delta) : "—"}
          sub={dec ? `${pct(dec.share_significant, 0)} of cells beyond 2 SE` : undefined} />
        <Kpi label="Accumulation mean ΔCE" value={acc ? signedPct(acc.mean_delta) : "—"}
          sub={acc ? `vs ${BENCHMARK_LABELS[acc.benchmark] ?? acc.benchmark}` : undefined} />
        <Kpi label="Data as of" value={cat.data?.as_of ?? "—"}
          sub={cat.data ? (cat.data.wrds ? "WRDS + public sources" : "Public sources · WRDS pending") : "connecting…"} />
      </div>

      <BentoGrid className="max-w-none md:auto-rows-[15rem]">
        <Tile href="/lab" className="md:col-span-2" title="01 Multi-Asset Research Lab"
          description="Return moments, drawdowns, rolling and regime-conditional correlation, joint-loss frequencies, DCC, t-copula tails, Markov-switching regimes, factor exposures."
          icon={<IconChartDots3 className="h-4 w-4 text-muted-foreground" />}
          header={<div className="grid flex-1 grid-cols-2 gap-2">
            <Kpi label="Core universe" value={core?.window ? core.window[0].slice(0, 4) + "–" + core.window[1].slice(0, 4) : "—"} sub={core?.assets?.length ? core.assets.length + " assets" : undefined} />
            <Kpi label="Modern universe" value={modern?.window ? modern.window[0].slice(0, 4) + "–" + modern.window[1].slice(0, 4) : "—"} sub={modern?.assets?.length ? modern.assets.length + " assets" : undefined} />
          </div>} />
        <Tile href="/simulate" title="02 Lifecycle Simulator"
          description="Investor builder across accumulation and decumulation; wealth and consumption fan charts."
          icon={<IconChartAreaLine className="h-4 w-4 text-muted-foreground" />}
          header={<Kpi label="Runs" value={ov.data?.counts?.experiment ?? "—"} sub="experiments in the registry" />} />
        <Tile href="/optimize" title="03 Utility & Policy Optimizer"
          description="Constant-mix, glidepath, risk parity, CVaR, regime-dependent, parametric and grid-DP policies."
          icon={<IconFlask2 className="h-4 w-4 text-muted-foreground" />}
          header={<Kpi label="Policies" value="12" sub="static, dynamic and DP" />} />
        <Tile href="/withdrawal-lab" title="04 Withdrawal-Rate Lab"
          description="The signature view: ΔCE by withdrawal rate × years relative to retirement; accumulation by savings rate × age."
          icon={<IconTable className="h-4 w-4 text-muted-foreground" />}
          header={<Kpi label="Sweeps" value={ov.data?.counts?.sweep ?? "—"} sub="cached surfaces" />} />
        <Tile href="/compare" title="05 Strategy Comparison & Validation"
          description="Paired ΔCE on common paths, divergent-path explorer, cohort replay, uncertainty bands, Shapley MU."
          icon={<IconGitCompare className="h-4 w-4 text-muted-foreground" />}
          header={<Kpi label="Validations" value={ov.data?.counts?.validation ?? "—"} sub="robustness checks run" />} />
      </BentoGrid>
    </div>
  );
}
