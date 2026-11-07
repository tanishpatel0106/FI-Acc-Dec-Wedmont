import { Suspense } from "react";
import { Research } from "@/components/pages/v2/Research";

export default function Page() {
  return (
    <Suspense>
      <Research />
    </Suspense>
  );
}
