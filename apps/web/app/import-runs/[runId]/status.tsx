"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import type { ImportRun } from "@/lib/api-contract";
import { readImportRun } from "@/lib/api-contract";
import { ensureAlphaTestSession } from "@/lib/session";

type RunView =
  | { readonly kind: "loading" }
  | { readonly kind: "loaded"; readonly run: ImportRun }
  | { readonly kind: "error"; readonly message: string };

export function ImportRunStatus({ runId }: { readonly runId: string }) {
  const [runView, setRunView] = useState<RunView>({ kind: "loading" });

  useEffect(() => {
    let active = true;

    async function loadRun() {
      try {
        const session = ensureAlphaTestSession(window.localStorage);
        const run = await readImportRun(runId, session);
        if (active) {
          setRunView({ kind: "loaded", run });
        }
      } catch (error) {
        if (active) {
          setRunView({
            kind: "error",
            message: error instanceof Error ? error.message : "Unknown import status error"
          });
        }
      }
    }

    void loadRun();

    return () => {
      active = false;
    };
  }, [runId]);

  if (runView.kind === "loading") {
    return (
      <section className="status-panel" aria-live="polite">
        <h1>Loading import status</h1>
        <p>The last known import state will remain visible while polling catches up.</p>
      </section>
    );
  }

  if (runView.kind === "error") {
    return (
      <section className="status-panel">
        <StatusPill tone="error">Status unavailable</StatusPill>
        <h1>Import status error</h1>
        <p>{runView.message}</p>
      </section>
    );
  }

  return (
    <section className="status-grid" aria-labelledby="run-title">
      <div className="status-panel">
        <StatusPill tone="info">Import queued</StatusPill>
        <h1 id="run-title">Import run</h1>
        <p>
          Run <span className="mono">{runView.run.runId}</span> is queued for worker processing.
          Credential version {runView.run.credentialVersion} is referenced without exposing secret
          values.
        </p>
        <p>
          <Link href={`/leagues/${runView.run.leagueUuid}`}>Open league dashboard</Link>
        </p>
        <dl className="run-metrics">
          <div>
            <dt>State</dt>
            <dd>{runView.run.state}</dd>
          </div>
          <div>
            <dt>Current step</dt>
            <dd>{runView.run.currentStep}</dd>
          </div>
          <div>
            <dt>Warnings</dt>
            <dd>{runView.run.warningCount}</dd>
          </div>
        </dl>
      </div>
      <div className="timeline-panel">
        <h2>Step timeline</h2>
        <ul className="timeline">
          {runView.run.steps.map((step) => (
            <li key={step.name}>
              <span className="mono">{step.state}</span>
              <span>{step.detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
