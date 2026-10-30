import { Suspense } from "react";
import { Simulator } from "@/components/pages/Simulator";

export default function Page() {
  return (
    <Suspense>
      <Simulator />
    </Suspense>
  );
}
