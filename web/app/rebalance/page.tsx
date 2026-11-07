import { Suspense } from "react";
import { Rebalance } from "@/components/pages/v2/Rebalance";

export default function Page() {
  return (
    <Suspense>
      <Rebalance />
    </Suspense>
  );
}
