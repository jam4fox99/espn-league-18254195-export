"use client";

import { useCallback } from "react";
import { EvidenceList, LeagueNav, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import { type FormulaData, readFormula } from "@/lib/product-api";
import { formulaVersion } from "@/lib/product-model";
import type { AlphaSession } from "@/lib/session";

// Fallback for older snapshots that predate the live-weights payload (and the e2e
// formula mock, which serves no weights). The live V3 table below supersedes this
// whenever the API returns a non-empty `weights` map.
const approvedWeights = [
  {
    label: "Trade performance",
    value: "35%",
    detail: "Retrospective value captured from eligible trade rows."
  },
  {
    label: "Waiver/free-agent performance",
    value: "35%",
    detail: "Eligible waiver and free-agent add/drop impact."
  },
  {
    label: "Record and points-for",
    value: "20%",
    detail: "Completed-season record and points context."
  },
  {
    label: "Luck-adjusted performance",
    value: "10%",
    detail: "Actual record compared with schedule-adjusted expectations."
  }
] as const;

// Per-component "what it measures" copy, keyed by the v3 component keys the worker emits.
const COMPONENT_DETAIL: Record<string, string> = {
  tradeValue: "Net Value Over Replacement captured (or lost) in completed trades.",
  waiverValue: "Rest-of-season VOR added through waiver and free-agent moves.",
  lineupEfficiency: "Points started versus the optimal lineup each week.",
  recordAndPoints: "Completed-season record blended with points-for.",
  draftValue: "Draft-pick VOR surplus over the pooled slot-value curve.",
  luck: "Point differential percentile — schedule-driven over/underperformance."
};

type LiveWeight = {
  readonly key: string;
  readonly label: string;
  readonly value: string;
  readonly detail: string;
};

function liveWeights(formula: FormulaData): readonly LiveWeight[] {
  return Object.entries(formula.weights)
    .filter(([, weight]) => weight > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([key, weight]) => ({
      key,
      label: formula.componentLabels[key] ?? key,
      value: `${Math.round(weight * 100)}%`,
      detail: COMPONENT_DETAIL[key] ?? "Weighted component of the retrospective GM rating."
    }));
}

export function FormulaPage({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback((session: AlphaSession) => readFormula(session, leagueId), [leagueId]);

  return (
    <ProductLoader load={load}>
      {(formula) => {
        const live = liveWeights(formula);
        const weights = live.length > 0 ? live : null;
        return (
          <section className="product-stack">
            <LeagueNav leagueId={leagueId} />
            <ProductHeader eyebrow="Formula" leagueId={leagueId} title="Formula and provenance">
              <StatusPill tone="info">Retrospective only</StatusPill>
            </ProductHeader>
            <article className="product-panel">
              <h2>Score model provenance</h2>
              <EvidenceList
                items={[
                  { label: "Formula version", value: formulaVersion(formula) },
                  {
                    label: "Provenance",
                    value: formula.provenance ?? formula.scoreModels.join(", ")
                  },
                  { label: "Career caveat", value: formula.caveat }
                ]}
              />
            </article>
            <table className="data-table">
              <caption>
                {weights ? `${formula.label ?? "GM rating"} weights` : "Approved V1 weights"}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Component</th>
                  <th scope="col">Weight</th>
                  <th scope="col">Usage</th>
                </tr>
              </thead>
              <tbody>
                {weights
                  ? weights.map((weight) => (
                      <tr key={weight.key}>
                        <th scope="row">{weight.label}</th>
                        <td>{weight.value}</td>
                        <td>{weight.detail}</td>
                      </tr>
                    ))
                  : approvedWeights.map((weight) => (
                      <tr key={weight.label}>
                        <th scope="row">{weight.label}</th>
                        <td>{weight.value}</td>
                        <td>{weight.detail}</td>
                      </tr>
                    ))}
                {weights ? null : (
                  <tr>
                    <th scope="row">Draft grade</th>
                    <td>Excluded</td>
                    <td>Draft and ADP data are absent from V1, so no draft score is fabricated.</td>
                  </tr>
                )}
              </tbody>
            </table>
            <article className="product-panel">
              <h2>Current source models</h2>
              <p>{formula.scoreModels.join(", ")}</p>
            </article>
          </section>
        );
      }}
    </ProductLoader>
  );
}
