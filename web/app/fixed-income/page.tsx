import { Suspense } from "react";
import { FixedIncome } from "@/components/pages/FixedIncome";

export default function Page() {
  return (
    <Suspense>
      <FixedIncome />
    </Suspense>
  );
}
