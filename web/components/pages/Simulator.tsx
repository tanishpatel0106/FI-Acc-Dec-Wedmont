"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";
import { PageHeader, Section } from "@/components/common/Section";
import { InvestorForm } from "@/components/experiment/InvestorForm";
import { RunProgress } from "@/components/experiment/RunProgress";
import { ResultSummary } from "@/components/experiment/ResultSummary";
import { apiPost } from "@/lib/api/client";
import { useResults, useRunStatus } from "@/lib/api/hooks";
import { builderFromQuery, builderToQuery, specFromBuilder, useBuilder } from "@/lib/store";

export function Simulator() {
  const s = useBuilder();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const hydrated = useRef(false);
  const [ready, setReady] = useState(false);
  const [runId, setRunId] = useState<string | null>(params.get("run"));
  const [watching, setWatching] = useState<string | null>(null);
  const status = useRunStatus(runId);
  const results = useResults(runId, status.data?.status === "done");

  // URL search params mirror the active spec so any view is shareable
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    s.set(builderFromQuery(new URLSearchParams(params.toString())));
    setReady(true);
  }, [params, s]);
  useEffect(() => {
    if (!hydrated.current) return;
    const { set: _set, ...state } = s;
    void _set;
    const q = builderToQuery(state);
    const next = q + (runId ? (q ? "&" : "") + "run=" + runId : "");
    router.replace(pathname + (next ? "?" + next : ""), { scroll: false });
  }, [s, runId, router, pathname]);

  const onDone = useCallback((stage: string) => {
    setWatching(null);
    if (stage === "failed") toast.error("Run failed — see Runs & Reports for the error");
    status.refetch();
  }, [status]);

  async function run() {
    const { set: _set, ...state } = s;
    void _set;
    try {
      const res = await apiPost<{ status: string }>("/v1/experiments", specFromBuilder(state));
      setRunId(res.run_id);
      if (res.status === "done") toast.success("Cache hit — identical spec already computed");
      else setWatching(res.run_id);
    } catch (e) {
      toast.error(String((e as Error).message));
    }
  }

  return (
    <div>
      <PageHeader eyebrow="02" title="Lifecycle Simulator"
        description="One engine for accumulation and decumulation: CGM labor income, retirement pension, spending rules, rebalancing costs and SSA mortality, evaluated against a benchmark on common random numbers.">
        <HoverBorderGradient onClick={run} containerClassName="rounded-full" className="bg-background px-5 py-2 text-sm text-foreground">
          Run experiment
        </HoverBorderGradient>
      </PageHeader>
      <RunProgress runId={watching} onDone={onDone} />
      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Section className="h-fit lg:sticky lg:top-0">
          {ready ? <InvestorForm /> : <div className="h-96 animate-pulse rounded-lg bg-muted/40" />}
        </Section>
        <div className="min-w-0">
          {status.data?.status === "failed" ? (
            <Section title="Run failed"><pre className="whitespace-pre-wrap text-xs text-destructive">{status.data.error}</pre></Section>
          ) : null}
          {results.data ? (
            <ResultSummary r={results.data.results} runId={runId} retireAge={s.retirementAge} />
          ) : (
            <Section>
              <div className="flex h-80 flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
                {runId && status.data && status.data.status !== "done" ? (
                  <span>Run {runId.slice(0, 10)} is {status.data.stage.replace(/_/g, " ")} ({Math.round(status.data.progress * 100)}%)…</span>
                ) : (
                  <>
                    <span>Configure an investor and press <b>Run experiment</b>.</span>
                    <span className="text-xs">Identical specifications are answered from the cache by their SHA-256 run ID.</span>
                  </>
                )}
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}
