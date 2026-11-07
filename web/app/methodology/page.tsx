import { Suspense } from "react";
import { MethodologyV2 } from "@/components/pages/v2/MethodologyV2";

export default function Page() {
  return (
    <Suspense>
      <MethodologyV2 />
    </Suspense>
  );
}
