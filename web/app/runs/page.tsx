import { Suspense } from "react";
import { Runs } from "@/components/pages/Runs";

export default function Page() {
  return (
    <Suspense>
      <Runs />
    </Suspense>
  );
}
