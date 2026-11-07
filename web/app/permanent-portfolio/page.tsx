import { Suspense } from "react";
import { PermanentPortfolio } from "@/components/pages/PermanentPortfolio";

export default function Page() {
  return (
    <Suspense>
      <PermanentPortfolio />
    </Suspense>
  );
}
