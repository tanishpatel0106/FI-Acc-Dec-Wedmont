import { Suspense } from "react";
import { ResearchLab } from "@/components/pages/ResearchLab";

export default function Page() {
  return (
    <Suspense>
      <ResearchLab />
    </Suspense>
  );
}
