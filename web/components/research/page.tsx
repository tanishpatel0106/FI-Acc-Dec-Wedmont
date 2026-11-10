"use client";
import Link from "next/link";
import { createContext, useContext, useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { IconChevronDown } from "@tabler/icons-react";
import { PAGE_BY_KEY, pageHref, type PageKey } from "@/lib/research/routes";
import { useResearchContext } from "@/lib/store";
import { cn } from "@/lib/utils";
import { pageIcon } from "@/components/shell/icons";

const SectionCtx = createContext<{ active: string | null }>({ active: null });

/** The active research section of the current page (null when the page has no sections). */
export function useActiveSection(): string | null {
  return useContext(SectionCtx).active;
}

/**
 * Renders its children only while one of the given sections is active. Sections are the page's own
 * domain-named areas (?section=…); only the active one is mounted so no hidden chart computes.
 */
export function Sec({ id, children }: { id: string | string[]; children: React.ReactNode }) {
  const active = useActiveSection();
  const ids = Array.isArray(id) ? id : [id];
  if (active !== null && !ids.includes(active)) return null;
  return <div data-section={ids.join(" ")} className="space-y-4">{children}</div>;
}

export function useSection(page: PageKey, fallback?: string): [string | null, (s: string) => void] {
  const info = PAGE_BY_KEY[page];
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const q = params.get("section");
  const active = info.sections.length === 0 ? null : info.sections.some((s) => s.id === q) ? q! : fallback && info.sections.some((s) => s.id === fallback) ? fallback : info.sections[0].id;
  const set = (s: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("section", s);
    router.replace(pathname + "?" + next.toString(), { scroll: false });
  };
  return [active, set];
}

function HowToUse({ page }: { page: PageKey }) {
  const p = PAGE_BY_KEY[page];
  return (
    <details className="group mt-3 rounded-lg border border-border bg-card/50 text-xs" data-testid="how-to-use">
      <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 font-medium">
        How to use this page
        <IconChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
      </summary>
      <div className="grid gap-4 border-t border-border px-3 py-3 md:grid-cols-3">
        <div>
          <div className="mb-1 font-semibold text-muted-foreground">Steps</div>
          <ol className="list-decimal space-y-0.5 pl-4">{p.howTo.map((h) => <li key={h}>{h}</li>)}</ol>
        </div>
        <div>
          <div className="mb-1 font-semibold text-muted-foreground">What you can do here</div>
          <ul className="list-disc space-y-0.5 pl-4">{p.canDo.map((h) => <li key={h}>{h}</li>)}</ul>
          <div className="mb-1 mt-2 font-semibold text-muted-foreground">A useful result looks like</div>
          <p>{p.goodResult}</p>
        </div>
        <div>
          <div className="mb-1 font-semibold text-muted-foreground">Read with care</div>
          <ul className="list-disc space-y-0.5 pl-4">{p.limitations.map((h) => <li key={h}>{h}</li>)}</ul>
        </div>
      </div>
    </details>
  );
}

const pct = (x: number) => (x * 100).toFixed(1) + "%";

/** The shared research context every page reads: shown so the user always knows which assumptions apply. */
export function ContextRibbon() {
  const c = useResearchContext();
  const items: [string, string][] = [
    ["Universe", c.universe], ["Generator", c.generator], ["Paths", String(c.nPaths)], ["Age", String(c.retirementAge)],
    ["Horizon", c.horizonYears + "y"], ["Wealth", "$" + Math.round(c.wealth / 1000) + "k"], ["Withdrawal", pct(c.withdrawalRate)],
    ["γ", String(c.gamma)], ["Costs", c.costBps + " bps"], ["Benchmark", c.benchmark],
  ];
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-dashed border-border px-3 py-1.5 text-[11px]"
      role="status" aria-label="Shared research context" data-testid="context-ribbon">
      <span className="font-medium text-muted-foreground">Research context</span>
      {items.map(([k, v]) => <span key={k} className="whitespace-nowrap"><span className="text-muted-foreground">{k}</span> <span className="font-medium">{v}</span></span>)}
      <span className="text-muted-foreground">· persisted studies show their own run spec in each chart&apos;s info panel</span>
    </div>
  );
}

function SectionNav({ page, active, onChange }: { page: PageKey; active: string; onChange: (s: string) => void }) {
  const p = PAGE_BY_KEY[page];
  return (
    <nav aria-label={p.name + " sections"} className="sticky top-14 z-30 -mx-1 mt-4 overflow-x-auto bg-background/90 px-1 py-2 backdrop-blur">
      <div role="tablist" className="flex gap-1">
        {p.sections.map((s) => (
          <button key={s.id} role="tab" aria-selected={s.id === active} aria-controls={"sec-" + s.id} id={"tab-" + s.id}
            data-section-tab={s.id} title={s.summary} onClick={() => onChange(s.id)}
            className={cn("whitespace-nowrap rounded-full border px-3 py-1 text-xs transition-colors",
              s.id === active ? "border-foreground/40 bg-foreground/10 text-foreground" : "border-border text-muted-foreground hover:bg-muted hover:text-foreground")}>
            {s.title}
          </button>
        ))}
      </div>
    </nav>
  );
}

function Related({ page }: { page: PageKey }) {
  const p = PAGE_BY_KEY[page];
  return (
    <aside className="mt-10 border-t border-border pt-4" aria-label="Related pages">
      <div className="mb-2 text-xs font-semibold text-muted-foreground">Related research pages</div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {p.related.map((k) => {
          const r = PAGE_BY_KEY[k];
          const Icon = pageIcon(r.icon);
          return (
            <Link key={k} href={pageHref(k)} className="rounded-lg border border-border p-3 text-xs hover:bg-muted">
              <div className="flex items-center gap-2 font-medium"><Icon className="h-4 w-4" />{r.name}</div>
              <div className="mt-1 text-muted-foreground">{r.question}</div>
            </Link>
          );
        })}
      </div>
    </aside>
  );
}

/**
 * Common page layout: title, research question, how-to, controls, shared context ribbon, section
 * navigation, the active section, related pages. Deep links: ?section=<id>#<VIZ-ID>.
 */
export function ResearchPage({ page, intro, controls, children, ribbon = true, defaultSection }: {
  page: PageKey; intro?: React.ReactNode; controls?: React.ReactNode; children: React.ReactNode; ribbon?: boolean; defaultSection?: string;
}) {
  const p = PAGE_BY_KEY[page];
  const [active, setActive] = useSection(page, defaultSection);
  const sec = p.sections.find((s) => s.id === active);
  useEffect(() => {
    const h = typeof window !== "undefined" ? window.location.hash.slice(1) : "";
    if (!h) return;
    const t = window.setTimeout(() => document.getElementById(h)?.scrollIntoView({ block: "start" }), 400);
    return () => window.clearTimeout(t);
  }, [active]);
  return (
    <div data-page={page}>
      <header>
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{p.group}</div>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{p.name}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{p.question}</p>
        {intro ? <div className="mt-2 max-w-3xl text-sm">{intro}</div> : null}
        <HowToUse page={page} />
        {ribbon ? <ContextRibbon /> : null}
        {controls ? <div className="mt-3">{controls}</div> : null}
      </header>
      {active && sec ? <SectionNav page={page} active={active} onChange={setActive} /> : null}
      <SectionCtx.Provider value={{ active }}>
        <div className="mt-4" id={active ? "sec-" + active : undefined} role={active ? "tabpanel" : undefined} aria-labelledby={active ? "tab-" + active : undefined}>
          {sec ? <p className="mb-4 text-xs text-muted-foreground"><span className="font-medium text-foreground">{sec.title}.</span> {sec.summary}</p> : null}
          {children}
        </div>
      </SectionCtx.Provider>
      <Related page={page} />
    </div>
  );
}
