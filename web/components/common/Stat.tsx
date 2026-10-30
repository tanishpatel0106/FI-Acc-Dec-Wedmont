import { cn } from "@/lib/utils";

export function Stat({
  label,
  value,
  sub,
  tone,
  className,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "pos" | "neg" | "muted";
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-border bg-card p-4", className)}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-1 text-2xl font-semibold tabular-nums tracking-tight",
          tone === "muted" && "text-muted-foreground",
        )}
      >
        {value}
      </div>
      {sub ? <div className="mt-1 text-xs text-muted-foreground tabular-nums">{sub}</div> : null}
    </div>
  );
}
