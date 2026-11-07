import { Suspense } from "react";
import { MarketState } from "@/components/pages/MarketState";

export default function Page() {
  return (
    <Suspense>
      <MarketState />
    </Suspense>
  );
}
