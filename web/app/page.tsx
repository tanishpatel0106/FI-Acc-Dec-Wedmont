import { Suspense } from "react";
import { OverviewV2 } from "@/components/pages/v2/OverviewV2";

export default function Page() {
  return (
    <Suspense>
      <OverviewV2 />
    </Suspense>
  );
}
