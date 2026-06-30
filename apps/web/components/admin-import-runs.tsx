"use client";

import { useCallback } from "react";
import { ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { readAdminImportRuns } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

export function AdminImportRuns() {
  const load = useCallback((session: AlphaSession) => readAdminImportRuns(session), []);

  return (
    <ProductLoader load={load}>
      {(data) => (
        <section className="product-stack">
          <ProductHeader eyebrow="Internal admin" title="Import runs" />
          <table className="data-table">
            <caption>Internal import job status</caption>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">League</th>
                <th scope="col">Status</th>
                <th scope="col">Step</th>
                <th scope="col">Warnings</th>
              </tr>
            </thead>
            <tbody>
              {data.runs.map((run) => (
                <tr key={run.runId}>
                  <th scope="row" className="mono">
                    {run.runId}
                  </th>
                  <td className="mono">{run.leagueId}</td>
                  <td>{run.status}</td>
                  <td>{run.step}</td>
                  <td>{run.warnings.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </ProductLoader>
  );
}
