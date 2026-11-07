import { Suspense } from "react";
import { WithdrawalLab } from "@/components/pages/WithdrawalLab";

export default function Page() {
  return (
    <Suspense>
      <WithdrawalLab />
    </Suspense>
  );
}
