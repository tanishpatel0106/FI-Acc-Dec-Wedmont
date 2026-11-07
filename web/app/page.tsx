import { Suspense } from "react";
import { Overview } from "@/components/pages/Overview";

export default function Page() {
  return (
    <Suspense>
      <Overview />
    </Suspense>
  );
}
