"use client";
import Link from "next/link";
import { useState } from "react";
import { IconArrowRight, IconChevronRight } from "@tabler/icons-react";
import { Spotlight } from "@/components/ui/spotlight";
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";
import { Viz, DataTable } from "@/components/research/kit";
import { pageIcon } from "@/components/shell/icons";
import { JOURNEYS, NAV_GROUPS, PAGES, PAGE_BY_KEY, QUESTIONS, WORKFLOW, pageHref } from "@/lib/research/routes";
import { VIZ_BY_ID, vizHref } from "@/lib/research/visualization-registry";
import { useV2 } from "@/lib/api/v2";
import { cn } from "@/lib/utils";

/* eslint-disable @typescript-eslint/no-explicit-any */
export const RESEARCH_QUESTION =
  "When, why and in which form does defensive allocation improve lifetime sustainability as an investor moves from net contributions to net withdrawals — and what is that worth in certainty-equivalent consumption?";

export function Hero() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-card px-6 py-10 md:px-10" data-testid="hero">
      <Spotlight className="-top-40 left-0 md:-top-20 md:left-60" fill="#3987e5" />
      <div className="relative z-10 max-w-4xl">
        <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Wedmont Private Capital × Columbia · research application</div>
        <h1 className="mt-3 text-3xl font-semibold tracking-[0.2em]">LIFECYCLE</h1>
        <p className="mt-1 text-lg font-medium">Quantitative Portfolio Research Across Accumulation and Decumulation</p>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground"><span className="font-medium text-foreground">Research question.</span> {RESEARCH_QUESTION}</p>
        <p className="mt-2 text-sm text-muted-foreground">
          One application for withdrawal risk, lifecycle cash flows, portfolio construction, fixed income, market state, scenarios and statistical validation.
          Every number comes from a persisted, hashed backend run; anything not yet computed says so.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href={pageHref("withdrawal", "overview")}>
            <HoverBorderGradient as="div" containerClassName="rounded-full" className="bg-background px-5 py-2 text-sm text-foreground">Explore Withdrawal Risk →</HoverBorderGradient>
          </Link>
          <Link href={pageHref("lifecycle", "simulator")} className="rounded-full border border-border px-5 py-2 text-sm hover:bg-muted">Run a Portfolio Simulation</Link>
          <Link href={pageHref("compare", "policies")} className="rounded-full border border-border px-5 py-2 text-sm hover:bg-muted">Compare Strategies</Link>
          <Link href={pageHref("research", "hypotheses")} className="rounded-full border border-border px-5 py-2 text-sm hover:bg-muted">Explore Research Results</Link>
        </div>
      </div>
    </div>
  );
}

/** "Which page should I use?" — one card per page, generated from the route registry. */
export function ApplicationGuide() {
  return (
    <section aria-labelledby="guide-h" className="space-y-4" data-testid="page-guide">
      <div>
        <h2 id="guide-h" className="text-lg font-semibold tracking-tight">Which page should I use?</h2>
        <p className="text-sm text-muted-foreground">Thirteen pages in four groups. Each card states the question the page answers, what you can do there and what a useful result looks like.</p>
      </div>
      {NAV_GROUPS.map((g) => (
        <div key={g} className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{g}</h3>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {PAGES.filter((p) => p.group === g).map((p) => {
              const Icon = pageIcon(p.icon);
              return (
                <article key={p.key} className="flex flex-col rounded-xl border border-border bg-card p-4 text-xs" data-guide-card={p.key}>
                  <div className="flex items-center gap-2 text-sm font-semibold"><Icon className="h-4 w-4" />{p.name}</div>
                  <p className="mt-1 text-muted-foreground">{p.question}</p>
                  <div className="mt-2 font-medium">You can</div>
                  <ul className="list-disc space-y-0.5 pl-4">{p.canDo.slice(0, 4).map((c) => <li key={c}>{c}</li>)}</ul>
                  <div className="mt-2"><span className="font-medium">Key analytics:</span> <span className="text-muted-foreground">{p.analytics.join(" · ")}</span></div>
                  <div className="mt-1"><span className="font-medium">A useful result:</span> <span className="text-muted-foreground">{p.goodResult}</span></div>
                  <div className="mt-auto pt-3">
                    {p.key === "overview" ? <span className="text-muted-foreground">You are here.</span> : (
                      <Link href={p.path} className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 hover:bg-muted" data-guide-link={p.path}>
                        Open {p.name} <IconArrowRight className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}

/** "What are you trying to find out?" — maps a research question to a page sequence, charts and configuration. */
export function QuestionNavigator() {
  const [sel, setSel] = useState(QUESTIONS[0].id);
  const q = QUESTIONS.find((x) => x.id === sel)!;
  const step = (s: { page: keyof typeof PAGE_BY_KEY; section?: string }) => {
    const p = PAGE_BY_KEY[s.page];
    const sec = p.sections.find((x) => x.id === s.section);
    return { href: pageHref(s.page, s.section), label: p.name + (sec ? " › " + sec.title : "") };
  };
  const start = step(q.start);
  return (
    <section aria-labelledby="nav-h" className="space-y-3" data-testid="question-navigator">
      <h2 id="nav-h" className="text-lg font-semibold tracking-tight">What are you trying to find out?</h2>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <div role="listbox" aria-label="Research questions" className="flex flex-col gap-1">
          {QUESTIONS.map((x) => (
            <button key={x.id} role="option" aria-selected={x.id === sel} onClick={() => setSel(x.id)} data-question={x.id}
              className={cn("flex items-center justify-between rounded-lg border px-3 py-2 text-left text-sm",
                x.id === sel ? "border-foreground/40 bg-foreground/5" : "border-border hover:bg-muted")}>
              {x.question}<IconChevronRight className="h-4 w-4 shrink-0" />
            </button>
          ))}
        </div>
        <div className="rounded-xl border border-border bg-card p-4 text-sm" aria-live="polite">
          <div className="font-semibold">{q.question}</div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <div className="text-xs font-semibold text-muted-foreground">Start here</div>
              <Link className="underline" href={start.href} data-nav-start={q.id}>{start.label}</Link>
              <div className="mt-2 text-xs font-semibold text-muted-foreground">Then</div>
              <ol className="list-decimal pl-5">{q.next.map((n) => { const s = step(n); return <li key={s.href}><Link className="underline" href={s.href}>{s.label}</Link></li>; })}</ol>
            </div>
            <div>
              <div className="text-xs font-semibold text-muted-foreground">Look at</div>
              <ul className="space-y-0.5">{q.charts.map((c) => <li key={c}><Link className="underline" href={vizHref(c)}><span className="font-mono text-xs">{c}</span> {VIZ_BY_ID[c]?.title ?? ""}</Link></li>)}</ul>
              <div className="mt-2 text-xs font-semibold text-muted-foreground">Configure</div>
              <p className="text-xs text-muted-foreground">{q.configure}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/** The research workflow as a stage diagram (OV-10). */
export function WorkflowDiagram() {
  return (
    <section aria-labelledby="wf-h" className="space-y-3">
      <h2 id="wf-h" className="text-lg font-semibold tracking-tight">How the research fits together</h2>
      <Viz id="OV-10" cls="illustrative">
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8" aria-label="Research workflow stages">
          {WORKFLOW.map((w, i) => (
            <li key={w.stage} className="relative flex flex-col rounded-lg border border-border bg-muted/20 p-3 text-xs">
              <div className="font-mono text-[10px] text-muted-foreground">{i + 1}</div>
              <div className="font-semibold">{w.stage}</div>
              <p className="mt-1 text-muted-foreground">{w.description}</p>
              <div className="mt-auto flex flex-wrap gap-x-2 pt-2">{w.pages.map((k) => <Link key={k} className="underline" href={pageHref(k)}>{PAGE_BY_KEY[k].name}</Link>)}</div>
              {i < WORKFLOW.length - 1 ? <IconArrowRight aria-hidden className="absolute -right-2.5 top-1/2 hidden h-4 w-4 -translate-y-1/2 text-muted-foreground xl:block" /> : null}
            </li>
          ))}
        </ol>
      </Viz>
    </section>
  );
}

/** Which persisted studies have a completed run (OV-11); registry lookup only. */
export function StudyStatus() {
  const st = useV2("/v1/studies");
  const rows = (st.data?.studies ?? []).map((s: any) => ({ ...s, latest: s.latest_done ?? null }));
  return (
    <Viz id="OV-11" cls="observed" empty={st.isError ? "API unreachable: start it with make api." : null}>
      <DataTable rows={rows} columns={[
        { key: "kind", label: "study" }, { key: "page", label: "page", fmt: (v) => <Link className="underline" href={v}>{v}</Link> },
        { key: "experiments", label: "experiments" },
        { key: "latest", label: "latest completed run", fmt: (v) => (v ? <Link className="font-mono underline" href={"/runs?section=registry&id=" + v}>{String(v).slice(0, 10)}</Link> : "Not computed") },
        { key: "latest_finished_at", label: "finished (UTC)", fmt: (v) => (v ? String(v).replace("T", " ").slice(0, 16) : "–") }]} />
    </Viz>
  );
}

/** Three guided research journeys. */
export function JourneyCards() {
  return (
    <section aria-labelledby="jr-h" className="space-y-3" data-testid="journeys">
      <h2 id="jr-h" className="text-lg font-semibold tracking-tight">Quick-start research journeys</h2>
      <div className="grid gap-3 lg:grid-cols-3">
        {JOURNEYS.map((j) => (
          <article key={j.title} className="rounded-xl border border-border bg-card p-4 text-xs">
            <div className="text-sm font-semibold">{j.title}</div>
            <ol className="mt-2 space-y-2">
              {j.steps.map((s, i) => {
                const p = PAGE_BY_KEY[s.page];
                const sec = p.sections.find((x) => x.id === s.section);
                return (
                  <li key={i} className="flex gap-2">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border font-mono text-[10px]">{i + 1}</span>
                    <div><Link className="font-medium underline" href={pageHref(s.page, s.section)}>{p.name}{sec ? " › " + sec.title : ""}</Link>
                      <div className="text-muted-foreground">{s.goal}</div></div>
                  </li>
                );
              })}
            </ol>
          </article>
        ))}
      </div>
    </section>
  );
}
