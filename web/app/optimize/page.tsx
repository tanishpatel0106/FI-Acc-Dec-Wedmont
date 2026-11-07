import { Suspense } from "react";
import { OptimizeV2 } from "@/components/pages/v2/OptimizeV2";

export default function Page() {
  return (
    <Suspense>
      <OptimizeV2 />
    </Suspense>
  );
}
