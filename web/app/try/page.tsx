import { Suspense } from "react";
import { TryFlow } from "./TryFlow";

export default function TryPage() {
  return (
    <Suspense fallback={<p role="status">Opening Try it…</p>}>
      <TryFlow />
    </Suspense>
  );
}
