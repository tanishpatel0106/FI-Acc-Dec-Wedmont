"use client";
import { useEffect, useState } from "react";
import { MultiStepLoader } from "@/components/ui/multi-step-loader";
import { eventsUrl } from "@/lib/api/client";

const STAGES = ["queued", "generating_scenarios", "simulating", "optimising", "summarising"];
const LABELS = [
  { text: "Queued" },
  { text: "Generating scenario paths" },
  { text: "Simulating lifecycle" },
  { text: "Optimising policy" },
  { text: "Summarising results" },
];

/** Mirrors the backend SSE stages; the overlay can be dismissed while the run continues server-side. */
export function RunProgress({ runId, onDone }: { runId: string | null; onDone: (status: string) => void }) {
  const [stage, setStage] = useState<{ id: string | null; idx: number }>({ id: null, idx: 0 });
  const [closedFor, setClosedFor] = useState<string | null>(null);
  const stageIndex = stage.id === runId ? stage.idx : 0;
  const open = runId !== null && closedFor !== runId;

  useEffect(() => {
    if (!runId) return;
    const source = new EventSource(eventsUrl(runId));
    source.onmessage = (event) => {
      let payload = null;
      try { payload = JSON.parse(event.data); } catch { return; }
      if (!payload || typeof payload.stage !== "string") return;
      if (payload.stage === "done" || payload.stage === "failed" || payload.stage === "cancelled") {
        source.close();
        setClosedFor(runId);
        onDone(payload.stage);
        return;
      }
      for (let i = 0; i < STAGES.length; i++) {
        if (STAGES[i] === payload.stage) setStage({ id: runId, idx: i });
      }
    };
    source.onerror = () => { source.close(); setClosedFor(runId); onDone("unknown"); };
    return () => source.close();
  }, [runId, onDone]);

  return (
    <>
      <MultiStepLoader loadingStates={LABELS.slice(0, stageIndex + 1)} loading={open} duration={800} loop={false} />
      {open ? (
        <button
          onClick={() => setClosedFor(runId)}
          className="fixed right-6 top-6 z-[101] rounded-md border border-border bg-background/80 px-3 py-1 text-xs"
        >
          Hide (run continues)
        </button>
      ) : null}
    </>
  );
}

export function InlineProgress({ stage, progress }: { stage: string; progress: number }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{stage.replace(/_/g, " ")}</span>
        <span className="tabular-nums">{Math.round(progress * 100)}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-[var(--viz-s1)] transition-all" style={{ width: `${Math.max(progress * 100, 2)}%` }} />
      </div>
    </div>
  );
}
