import { Suspense } from "react";
import { LifecycleFlows } from "@/components/pages/v2/LifecycleFlows";

export default function Page() {
  return (
    <Suspense>
      <LifecycleFlows />
    </Suspense>
  );
}
