"use client";

import Link from "next/link";
import { useCallback } from "react";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { LeagueNav, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { TeamEmblem } from "@/components/team-emblem";
import type { RivalryMatrixData, RivalryMatrixEdge, RivalrySummary } from "@/lib/product-api";
import { readRivalries } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

export function RivalriesMatrix({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback((session: AlphaSession) => readRivalries(session, leagueId), [leagueId]);

  return (
    <ProductLoader load={load}>
      {(data) => (
        <section className="product-stack">
          <LeagueNav leagueId={leagueId} />
          <ProductHeader eyebrow="Rivalries" title="All-play matrix" />
          {data.managers.length === 0 ? (
            <p className="muted-note">No rivalry data is available for this snapshot.</p>
          ) : (
            <>
              <p className="muted-note">
                Each cell is the row manager's all-time win rate against the column manager. Greener
                is stronger; redder is a losing record.
              </p>
              <MatrixGrid leagueId={leagueId} data={data} />
              <NemesisTable summaries={data.summaries} />
            </>
          )}
        </section>
      )}
    </ProductLoader>
  );
}

function MatrixGrid({
  leagueId,
  data
}: {
  readonly leagueId: string;
  readonly data: RivalryMatrixData;
}) {
  const managers = data.managers;
  const edgeByPair = new Map<string, RivalryMatrixEdge>();
  for (const edge of data.edges) {
    if (edge.managerKey && edge.opponentKey) {
      edgeByPair.set(`${edge.managerKey}::${edge.opponentKey}`, edge);
    }
  }
  const columns = `170px repeat(${managers.length}, minmax(34px, 1fr))`;
  return (
    <div className="matrix-scroll">
      <div className="rivalry-matrix" style={{ gridTemplateColumns: columns }}>
        <span className="rivalry-matrix__corner" />
        {managers.map((manager, index) => (
          <span
            key={manager.managerKey}
            className="rivalry-matrix__colhead"
            title={manager.displayName}
          >
            {index + 1}
          </span>
        ))}
        {managers.map((rowManager, rowIndex) => (
          <MatrixRow
            key={rowManager.managerKey}
            leagueId={leagueId}
            rowIndex={rowIndex}
            rowManager={rowManager}
            managers={managers}
            edgeByPair={edgeByPair}
          />
        ))}
      </div>
    </div>
  );
}

function MatrixRow({
  leagueId,
  rowIndex,
  rowManager,
  managers,
  edgeByPair
}: {
  readonly leagueId: string;
  readonly rowIndex: number;
  readonly rowManager: RivalryMatrixData["managers"][number];
  readonly managers: RivalryMatrixData["managers"];
  readonly edgeByPair: Map<string, RivalryMatrixEdge>;
}) {
  const logoFor = useManagerLogo();
  return (
    <>
      <Link
        className="rivalry-matrix__rowhead"
        href={`/leagues/${leagueId}/gms/${encodeURIComponent(rowManager.managerKey)}`}
      >
        <span className="rivalry-matrix__rownum">{rowIndex + 1}</span>
        <TeamEmblem logo={logoFor(rowManager.managerKey)} name={rowManager.displayName} size={22} />
        {rowManager.displayName}
      </Link>
      {managers.map((colManager) => {
        if (colManager.managerKey === rowManager.managerKey) {
          return <span key={colManager.managerKey} className="rivalry-cell rivalry-cell--self" />;
        }
        const edge = edgeByPair.get(`${rowManager.managerKey}::${colManager.managerKey}`);
        if (!edge || edge.games === undefined || edge.games === 0) {
          return (
            <span key={colManager.managerKey} className="rivalry-cell rivalry-cell--empty">
              ·
            </span>
          );
        }
        const winPct = edge.winPct ?? 0;
        return (
          <span
            key={colManager.managerKey}
            className="rivalry-cell"
            style={{ background: winColor(winPct) }}
            title={`${rowManager.displayName} vs ${colManager.displayName}: ${edge.wins ?? 0}-${edge.losses ?? 0}${edge.ties ? `-${edge.ties}` : ""} (${winPct.toFixed(0)}%)`}
          >
            {winPct.toFixed(0)}
          </span>
        );
      })}
    </>
  );
}

function NemesisTable({ summaries }: { readonly summaries: readonly RivalrySummary[] }) {
  const logoFor = useManagerLogo();
  if (summaries.length === 0) {
    return null;
  }
  const ordered = [...summaries].sort((a, b) => a.displayName.localeCompare(b.displayName));
  return (
    <article className="product-panel">
      <p className="section-kicker">Nemesis &amp; favorite opponent</p>
      <ul className="nemesis-table">
        <li className="nemesis-row nemesis-row--head">
          <span>Manager</span>
          <span>Favorite</span>
          <span>Nemesis</span>
        </li>
        {ordered.map((summary) => (
          <li key={summary.managerKey} className="nemesis-row">
            <span className="nemesis-row__name">
              <TeamEmblem logo={logoFor(summary.managerKey)} name={summary.displayName} size={22} />
              {summary.displayName}
            </span>
            <span className="nemesis-row__favorite">
              <EdgeCell edge={summary.favorite} />
            </span>
            <span className="nemesis-row__nemesis">
              <EdgeCell edge={summary.nemesis} />
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function EdgeCell({ edge }: { readonly edge: RivalrySummary["favorite"] }) {
  const logoFor = useManagerLogo();
  if (!edge?.opponentDisplayName) {
    return <>—</>;
  }
  const pct = edge.winPct ?? 0;
  return (
    <span className="nemesis-edge">
      <TeamEmblem logo={logoFor(edge.opponentKey)} name={edge.opponentDisplayName} size={20} />
      <span>
        {edge.opponentDisplayName} ({edge.wins ?? 0}-{edge.losses ?? 0}, {pct.toFixed(0)}%)
      </span>
    </span>
  );
}

function winColor(winPct: number): string {
  const delta = Math.max(-1, Math.min(1, (winPct - 50) / 50));
  if (delta >= 0) {
    return `rgba(34, 197, 130, ${(0.12 + delta * 0.5).toFixed(3)})`;
  }
  return `rgba(248, 113, 113, ${(0.12 + Math.abs(delta) * 0.5).toFixed(3)})`;
}
