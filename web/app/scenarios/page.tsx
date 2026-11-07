import { Suspense } from "react";
import { Scenarios } from "@/components/pages/v2/Scenarios";

export default function Page() {
  return (
    <Suspense>
      <Scenarios />
    </Suspense>
  );
}
