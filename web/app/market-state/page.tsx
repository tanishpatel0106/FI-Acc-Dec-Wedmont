import { Suspense } from "react";
import { MarketState } from "@/components/pages/v2/MarketState";

export default function Page() {
  return (
    <Suspense>
      <MarketState />
    </Suspense>
  );
}
