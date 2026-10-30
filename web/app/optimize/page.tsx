import { Suspense } from "react";
import { Optimizer } from "@/components/pages/Optimizer";

export default function Page() {
  return (
    <Suspense>
      <Optimizer />
    </Suspense>
  );
}
