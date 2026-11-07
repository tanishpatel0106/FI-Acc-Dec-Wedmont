import { Suspense } from "react";
import { FixedIncomeV2 } from "@/components/pages/v2/FixedIncomeV2";

export default function Page() {
  return (
    <Suspense>
      <FixedIncomeV2 />
    </Suspense>
  );
}
