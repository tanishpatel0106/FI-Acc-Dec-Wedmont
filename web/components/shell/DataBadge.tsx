"use client";
import { useCatalog } from "@/lib/api/hooks";
import { Badge } from "@/components/ui/badge";

export function DataBadge() {
  const { data, isError } = useCatalog();
  if (isError) return <Badge variant="destructive">API offline</Badge>;
  if (!data) return <Badge variant="outline">connecting…</Badge>;
  return (
    <div className="hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
      {data.synthetic ? <Badge variant="destructive">SYNTHETIC DATA</Badge> : null}
      <Badge variant="outline">{data.wrds ? "WRDS + public" : "Public data (WRDS pending)"}</Badge>
      <span>as of {data.as_of}</span>
      <span className="font-mono">cat {String(data.catalog_hash).slice(0, 8)}</span>
    </div>
  );
}
