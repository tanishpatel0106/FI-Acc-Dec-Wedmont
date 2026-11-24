import { Suspense } from "react";
import { Optimize } from "@/components/pages/Optimize";

export default function Page() {
  return (
    <Suspense>
      <Optimize />
    </Suspense>
  );
}
