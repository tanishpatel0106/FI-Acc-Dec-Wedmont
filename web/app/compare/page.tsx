import { Suspense } from "react";
import { Compare } from "@/components/pages/Compare";

export default function Page() {
  return (
    <Suspense>
      <Compare />
    </Suspense>
  );
}
