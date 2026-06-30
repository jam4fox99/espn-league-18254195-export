"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import type { AlphaSession } from "@/lib/session";
import { ensureAlphaTestSession } from "@/lib/session";

type LoadState<TData> =
  | { readonly kind: "loading" }
  | { readonly kind: "loaded"; readonly data: TData; readonly session: AlphaSession }
  | { readonly kind: "error"; readonly message: string };

export function ProductLoader<TData>({
  children,
  load
}: {
  readonly load: (session: AlphaSession) => Promise<TData>;
  readonly children: (data: TData, session: AlphaSession) => ReactNode;
}) {
  const [state, setState] = useState<LoadState<TData>>({ kind: "loading" });

  useEffect(() => {
    let active = true;

    async function loadData() {
      const session = ensureAlphaTestSession(window.localStorage);

      try {
        const data = await load(session);
        if (active) {
          setState({ kind: "loaded", data, session });
        }
      } catch (error) {
        if (active) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "League analytics unavailable."
          });
        }
      }
    }

    void loadData();
    return () => {
      active = false;
    };
  }, [load]);

  switch (state.kind) {
    case "loading":
      return (
        <section className="status-panel" aria-live="polite">
          <StatusPill tone="info">Loading</StatusPill>
          <h1>Loading league analytics</h1>
          <p>Last known league context remains protected while the current version loads.</p>
        </section>
      );
    case "error":
      return (
        <section className="status-panel">
          <StatusPill tone="error">Unavailable</StatusPill>
          <h1>Analytics unavailable</h1>
          <p>{state.message}</p>
        </section>
      );
    case "loaded":
      return <>{children(state.data, state.session)}</>;
    default:
      return assertNever(state);
  }
}

function assertNever(value: never): never {
  throw new Error(`Unhandled product loader state: ${JSON.stringify(value)}`);
}
