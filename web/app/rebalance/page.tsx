import { Suspense } from "react";
import { Rebalance } from "@/components/pages/Rebalance";

export default function Page() {
  return (
    <Suspense>
      <Rebalance />
    </Suspense>
  );
}
