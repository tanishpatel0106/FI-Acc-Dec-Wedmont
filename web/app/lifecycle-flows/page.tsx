import { Suspense } from "react";
import { LifecycleFlows } from "@/components/pages/LifecycleFlows";

export default function Page() {
  return (
    <Suspense>
      <LifecycleFlows />
    </Suspense>
  );
}
