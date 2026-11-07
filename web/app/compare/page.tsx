import { Suspense } from "react";
import { CompareV2 } from "@/components/pages/v2/CompareV2";

export default function Page() {
  return (
    <Suspense>
      <CompareV2 />
    </Suspense>
  );
}
