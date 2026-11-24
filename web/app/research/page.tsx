import { Suspense } from "react";
import { Research } from "@/components/pages/Research";

export default function Page() {
  return (
    <Suspense>
      <Research />
    </Suspense>
  );
}
