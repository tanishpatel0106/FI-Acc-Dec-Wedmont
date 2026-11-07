import { Suspense } from "react";
import { WithdrawalLabV2 } from "@/components/pages/v2/WithdrawalLabV2";

export default function Page() {
  return (
    <Suspense>
      <WithdrawalLabV2 />
    </Suspense>
  );
}
