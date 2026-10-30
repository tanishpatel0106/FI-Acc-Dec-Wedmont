"use client";
import { Tooltip } from "@/components/ui/tooltip-card";
import { Tex } from "./Tex";

export const METRICS: Record<string, { title: string; text: string; tex?: string }> = {
  CE: {
    title: "Certainty-equivalent consumption",
    text: "The constant real annual consumption that gives the same survival-weighted expected utility as the policy.",
    tex: String.raw`\mathrm{CE}=\left[\frac{(1-\gamma)\hat U}{\sum_t \beta^t S_t}\right]^{\frac{1}{1-\gamma}}`,
  },
  DCE: {
    title: "Utility gain ΔCE",
    text: "Percentage gain in CE over the benchmark, with a paired delta-method SE from common random numbers.",
    tex: String.raw`\Delta_{\mathrm{CE}}=\frac{\mathrm{CE}(\pi^*)}{\mathrm{CE}(\pi_{\mathrm{bench}})}-1`,
  },
  CVaR: {
    title: "CVaR 95% of shortfall",
    text: "Mean normalised spending shortfall in the worst 5% of paths (Rockafellar–Uryasev).",
    tex: String.raw`L_j=\sum_t \frac{(C_{j,t}-F_{j,t})_+}{C_{j,t}}`,
  },
  DV01: {
    title: "DV01",
    text: "Price change per 100 face for a 1bp move in yield.",
    tex: String.raw`\mathrm{DV01}=D_{\mathrm{mod}}\,P\times 10^{-4}`,
  },
  DUR: {
    title: "Modified duration & convexity",
    text: "Second-order price response to a yield change.",
    tex: String.raw`\frac{\Delta P}{P}\approx -D_{\mathrm{mod}}\Delta y+\tfrac12 C(\Delta y)^2`,
  },
  Q: {
    title: "Signed net-flow rate q",
    text: "Negative while accumulating, positive while decumulating.",
    tex: String.raw`q_t=\frac{C_t-Y_t-P_t}{W_{\mathrm{ref}}}`,
  },
  PDEP: {
    title: "Depletion probability",
    text: "Share of paths on which planned spending is ever not fully funded by the portfolio.",
  },
};

export function MetricLabel({ id, children }: { id: keyof typeof METRICS | string; children?: React.ReactNode }) {
  const m = METRICS[id];
  if (!m) return <span>{children ?? id}</span>;
  return (
    <Tooltip
      content={
        <div className="max-w-xs space-y-2 text-xs">
          <div className="font-semibold">{m.title}</div>
          <div className="text-muted-foreground">{m.text}</div>
          {m.tex ? <Tex>{m.tex}</Tex> : null}
        </div>
      }
    >
      <span className="cursor-help border-b border-dotted border-muted-foreground/60">{children ?? m.title}</span>
    </Tooltip>
  );
}
