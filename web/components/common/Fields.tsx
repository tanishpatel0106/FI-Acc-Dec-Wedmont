"use client";
import { cn } from "@/lib/utils";

export function Field({ label, hint, children, className }: { label: React.ReactNode; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={cn("flex flex-col gap-1 text-xs", className)}>
      <span className="text-muted-foreground">{label}</span>
      {children}
      {hint ? <span className="text-[10px] text-muted-foreground/80">{hint}</span> : null}
    </label>
  );
}

export function NativeSelect<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      className={cn(
        "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30",
        className,
      )}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value} className="bg-popover text-popover-foreground">
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function NumberInput({
  value,
  onChange,
  step,
  min,
  max,
  className,
  invalid,
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  className?: string;
  invalid?: boolean;
}) {
  return (
    <input
      type="number"
      value={Number.isFinite(value) ? value : ""}
      step={step}
      min={min}
      max={max}
      aria-invalid={invalid}
      onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))}
      className={cn(
        "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm tabular-nums outline-none focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive dark:bg-input/30",
        className,
      )}
    />
  );
}
