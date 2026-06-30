"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { ensureAlphaTestSession } from "@/lib/session";

type GateState = "checking" | "allowed";

export function AuthGate({ children }: { readonly children: ReactNode }) {
  const [gateState, setGateState] = useState<GateState>("checking");

  useEffect(() => {
    ensureAlphaTestSession(window.localStorage);
    setGateState("allowed");
  }, []);

  if (gateState === "allowed") {
    return <>{children}</>;
  }

  return (
    <section className="status-panel" aria-live="polite">
      <h1>Preparing alpha access</h1>
      <p>Preparing private alpha access before league data is displayed.</p>
    </section>
  );
}
