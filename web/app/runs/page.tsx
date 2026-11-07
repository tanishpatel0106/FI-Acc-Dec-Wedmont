import { Suspense } from "react";
import { RunsV2 } from "@/components/pages/v2/RunsV2";

export default function Page() {
  return (
    <Suspense>
      <RunsV2 />
    </Suspense>
  );
}
