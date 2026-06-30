"use client";

import { useCallback } from "react";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { InsightDeck, Workbench } from "@/components/product-insights";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import { readDataHealth } from "@/lib/product-api";
import { factsFromDataHealth } from "@/lib/product-model";
import type { AlphaSession } from "@/lib/session";

const requiredHealthRows = [
  {
    label: "Unresolved players",
    value: "Shown when present",
    detail: "Player rows without resolvable scoring context remain caveated instead of scored."
  },
  {
    label: "Incomplete trades",
    value: "Visible exclusions",
    detail: "Executed accepts missing grading inputs stay visible with score exclusion reasons."
  },
  {
    label: "Missing point rows",
    value: "Withheld",
    detail: "Rows missing rest-of-season or weekly points do not contribute to value captured."
  },
  {
    label: "Partial seasons",
    value: "Excluded from career",
    detail: "Partial/preseason seasons are kept out of career ratings."
  },
  {
    label: "FAAB/context",
    value: "Unavailable when zeroed",
    detail: "Auction context is displayed as unavailable instead of inferred."
  },
  {
    label: "Score exclusion reasons",
    value: "Required",
    detail: "Every withheld score category needs a visible reason."
  }
] as const;

export function DataHealthPage({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback(
    (session: AlphaSession) => readDataHealth(session, leagueId),
    [leagueId]
  );

  return (
    <ProductLoader load={load}>
      {(dataHealth) => {
        const facts = factsFromDataHealth(dataHealth);
        const ungradedExecutedAccepts = facts.ungradedExecutedAccepts;
        const ready =
          dataHealth.withheldScores.length > 0 &&
          facts.faabContext !== null &&
          facts.careerExcludedSeasons.includes(2026);
        return (
          <section className="product-stack">
            <LeagueNav leagueId={leagueId} />
            <ProductHeader eyebrow={dataHealth.modelName} leagueId={leagueId} title="Data health">
              <StatusPill tone={ready ? "success" : "warning"}>
                {ready ? "Caveats served" : "Caveats pending"}
              </StatusPill>
            </ProductHeader>
            <MetricStrip
              metrics={[
                {
                  label: "Ungraded executed accepts",
                  value:
                    ungradedExecutedAccepts === null
                      ? "Pending API field"
                      : ungradedExecutedAccepts.toString(),
                  detail:
                    "Executed accepts are withheld from scoring when grading inputs are incomplete."
                },
                {
                  label: "FAAB",
                  value: facts.faabContext ?? "Pending API field",
                  detail: "Waiver context is not inferred when auction data is unavailable."
                },
                {
                  label: "Career ratings",
                  value: facts.careerExcludedSeasons.includes(2026)
                    ? "2026 excluded"
                    : "Pending API field",
                  detail: "Partial/preseason rows do not enter career ratings."
                }
              ]}
            />
            <div className="product-grid">
              <article className="product-panel">
                <h2>Withheld scores</h2>
                {dataHealth.withheldScores.length > 0 ? (
                  <ul className="plain-list">
                    {dataHealth.withheldScores.map((score) => (
                      <li key={score}>{score}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Withheld score rows pending API fixture payload.</p>
                )}
              </article>
              <article className="product-panel">
                <h2>Caveats</h2>
                <ul className="plain-list">
                  {(facts.caveats.length > 0 ? facts.caveats : dataHealth.warnings).map(
                    (caveat) => (
                      <li key={caveat}>{caveat}</li>
                    )
                  )}
                </ul>
              </article>
            </div>
            <table className="data-table">
              <caption>Data-health coverage</caption>
              <thead>
                <tr>
                  <th scope="col">Surface</th>
                  <th scope="col">Status</th>
                  <th scope="col">Reason</th>
                </tr>
              </thead>
              <tbody>
                {requiredHealthRows.map((row) => (
                  <tr key={row.label}>
                    <th scope="row">{row.label}</th>
                    <td>{row.value}</td>
                    <td>{row.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <InsightDeck
              items={[
                {
                  label: "Health status",
                  value: ready ? "caveated" : "pending",
                  detail: "The current version is usable with caveats visible.",
                  tone: "warning"
                },
                {
                  label: "Withheld score types",
                  value: dataHealth.withheldScores.length.toString(),
                  detail: "Categories intentionally not scored with incomplete inputs.",
                  tone: "info"
                },
                {
                  label: "Caveats",
                  value: (dataHealth.caveats?.length ?? dataHealth.warnings.length).toString(),
                  detail: "User-visible warnings tied to the current analytics version.",
                  tone: "neutral"
                },
                {
                  label: "Career exclusion",
                  value: facts.careerExcludedSeasons.includes(2026) ? "2026" : "Pending",
                  detail: "Partial seasons stay outside career calculations.",
                  tone: "success"
                }
              ]}
            />
            <Workbench
              aside={
                <ul className="plain-list">
                  <li>Scores are retrospective value captured, not a projection.</li>
                  <li>Unavailable FAAB context is displayed rather than guessed.</li>
                  <li>Withheld rows remain visible for review.</li>
                </ul>
              }
              intro="This page is the trust layer for every score surface. It explains which rows are withheld, which inputs are caveated, and why partial 2026 data is excluded."
              title="Before trusting the rankings"
            >
              <table className="detail-table">
                <tbody>
                  <tr>
                    <th scope="row">FAAB context</th>
                    <td>
                      <strong>{facts.faabContext ?? "Pending API field"}</strong>
                      <p>Bid context is not inferred when ESPN export fields are always zero.</p>
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">Withheld scores</th>
                    <td>
                      <strong>{dataHealth.withheldScores.join(", ") || "None withheld"}</strong>
                      <p>These score categories stay withheld until the data supports them.</p>
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">Career boundary</th>
                    <td>
                      <strong>
                        {facts.careerExcludedSeasons.includes(2026)
                          ? "2026 excluded from career ratings"
                          : "Pending API field"}
                      </strong>
                      <p>Career ratings use completed season context only.</p>
                    </td>
                  </tr>
                </tbody>
              </table>
            </Workbench>
          </section>
        );
      }}
    </ProductLoader>
  );
}
