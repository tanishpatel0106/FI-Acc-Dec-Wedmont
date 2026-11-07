import { Suspense } from "react";
import { Scenarios } from "@/components/pages/Scenarios";

export default function Page() {
  return (
    <Suspense>
      <Scenarios />
    </Suspense>
  );
}
