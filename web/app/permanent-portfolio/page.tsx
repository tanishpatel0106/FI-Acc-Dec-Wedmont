import { Suspense } from "react";
import { PermanentPortfolio } from "@/components/pages/v2/PermanentPortfolio";

export default function Page() {
  return (
    <Suspense>
      <PermanentPortfolio />
    </Suspense>
  );
}
