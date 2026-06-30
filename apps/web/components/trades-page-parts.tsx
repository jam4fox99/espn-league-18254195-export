"use client";

import { ArrowLeftRight, Trophy } from "lucide-react";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { PlayerChip as PlayerHeadChip } from "@/components/player-image";
import { StatusPill } from "@/components/status-pill";
import { TeamEmblem } from "@/components/team-emblem";
import {
  formatSigned,
  numberField,
  rowCaveats,
  type SnapshotRow,
  stringField,
  type TradeAsset,
  type TradeSide,
  tradeSides
} from "@/components/transaction-page-utils";

const GRADE_BUCKETS = new Set(["A", "B", "C", "D", "F"]);

export function TradeList({ rows }: { readonly rows: readonly SnapshotRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <ArrowLeftRight aria-hidden="true" size={20} />
        <p>No trades match the selected filters.</p>
      </div>
    );
  }
  return (
    <div className="product-stack">
      {rows.map((row, index) => (
        <TradeCard key={rowKey(row, index)} row={row} />
      ))}
    </div>
  );
}

function vetoOf(row: SnapshotRow): { readonly percent: number; readonly band: string } | undefined {
  const raw = row["veto"];
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const record = raw as Record<string, unknown>;
    const percent = record["percent"];
    const band = record["band"];
    if (typeof percent === "number" && typeof band === "string") {
      return { percent, band };
    }
  }
  return undefined;
}

function VetoBadge({ percent, band }: { readonly percent: number; readonly band: string }) {
  const tone = band === "Collusion risk" ? "danger" : band === "Lean veto" ? "warn" : "ok";
  return (
    <span className={`veto-badge veto-badge--${tone}`}>
      Veto {Math.round(percent)}% · {band}
    </span>
  );
}

function TradeCard({ row }: { readonly row: SnapshotRow }) {
  const sides = tradeSides(row);
  const sideA = sides[0];
  const sideB = sides[1] ?? sides[0];
  const net = numberField(row, "netPoints");
  const season = numberField(row, "season");
  const caveats = rowCaveats(row);
  const eligible = booleanEligible(row);
  const tradeGrade = stringField(row, "tradeGrade");
  const veto = vetoOf(row);

  return (
    <article className="product-panel trade-card">
      <div className="trade-card__head">
        <div>
          <p className="section-kicker">{tradeWhen(row)}</p>
          <h2 className="trade-card__title">{tradeTitle(row)}</h2>
        </div>
        <div className="stat-row">
          {net !== undefined ? (
            <span className="stat-pill">
              Net swing <b>{formatSigned(net)}</b>
            </span>
          ) : null}
          {tradeGrade ? (
            <span className="stat-pill">
              Trade grade <Grade value={tradeGrade} />
            </span>
          ) : null}
          {veto ? <VetoBadge percent={veto.percent} band={veto.band} /> : null}
          <StatusPill tone={eligible ? "success" : "info"}>
            {eligible ? "Graded" : "Not scored"}
          </StatusPill>
        </div>
      </div>

      {sideA ? (
        <div className="trade-sides">
          <TradeSidePanel side={sideA} season={season} />
          <div className="trade-vs">
            <ArrowLeftRight aria-hidden="true" size={16} />
          </div>
          <TradeSidePanel side={sideB ?? sideA} season={season} />
        </div>
      ) : (
        <p className="muted-note">
          Trade participants and assets were not recoverable from the ESPN source.
        </p>
      )}

      {caveats.length > 0 ? (
        <ul className="plain-list">
          {caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function TradeSidePanel({
  side,
  season
}: {
  readonly side: TradeSide;
  readonly season: number | undefined;
}) {
  const logoFor = useManagerLogo();
  return (
    <section className={`trade-side${side.isWinner ? " is-winner" : ""}`}>
      <div className="trade-side__manager">
        <div className="trade-side__id">
          <TeamEmblem
            logo={logoFor(side.managerKey, season)}
            name={side.teamName ?? side.managerName}
            size={30}
          />
          <div className="who">
            <b>{side.managerName}</b>
            {side.teamName ? <span>{side.teamName}</span> : null}
          </div>
        </div>
        <Grade value={side.grade} />
      </div>
      <div className="stat-row">
        {side.isWinner ? (
          <span className="stat-pill">
            <Trophy aria-hidden="true" size={13} /> Objective winner
          </span>
        ) : null}
        {side.netPoints !== undefined ? (
          <span className="stat-pill">
            Value <b>{formatSigned(side.netPoints)}</b>
          </span>
        ) : null}
      </div>
      {side.assets.length > 0 ? (
        <ul className="player-list">
          {side.assets.map((asset) => (
            <PlayerChip key={asset.name} asset={asset} />
          ))}
        </ul>
      ) : (
        <p className="muted-note">No assets recorded.</p>
      )}
    </section>
  );
}

export function PlayerChip({
  asset,
  variant
}: {
  readonly asset: TradeAsset;
  readonly variant?: "add" | "drop";
}) {
  return (
    <li className={`player-chip${variant ? ` is-${variant}` : ""}`}>
      <PlayerHeadChip
        playerId={asset.playerId}
        name={asset.name}
        teamAbbr={asset.proTeamAbbrev}
        position={asset.position}
        isDST={asset.isDST}
        badge={asset.badge}
        size={32}
        trailing={asset.points !== undefined ? `${asset.points.toFixed(1)} pts` : "—"}
      />
    </li>
  );
}

// Collapse a letter grade ("A+", "B-", …) to its bucket; non-letter grades drop out.
export function tradeGradeBucket(grade: string | undefined): string | undefined {
  const letter = grade?.[0]?.toUpperCase();
  return letter && GRADE_BUCKETS.has(letter) ? letter : undefined;
}

export function tradeVetoBand(row: SnapshotRow): string | undefined {
  return vetoOf(row)?.band;
}

// Free-text haystack for a trade: both managers, their teams, and every asset name.
export function tradeSearchText(row: SnapshotRow): string {
  return tradeSides(row)
    .flatMap((side) => [
      side.managerName,
      side.teamName ?? "",
      ...side.assets.map((asset) => asset.name)
    ])
    .join(" ");
}

export function tradeId(row: SnapshotRow): string {
  return stringField(row, "tradeId") ?? stringField(row, "id") ?? "trade";
}

function rowKey(row: SnapshotRow, index: number): string {
  return stringField(row, "sourceTradeId") ?? `${tradeId(row)}-${index}`;
}

function Grade({ value }: { readonly value: string | undefined }) {
  const grade = value ?? "—";
  return (
    <span className="grade" data-grade={grade} title={`Trade grade ${grade}`}>
      {grade}
    </span>
  );
}

function tradeTitle(row: SnapshotRow): string {
  const [first, second] = tradeSides(row);
  if (first && second) {
    return `${first.managerName} ↔ ${second.managerName}`;
  }
  if (first) {
    return first.managerName;
  }
  const season = numberField(row, "season");
  return season ? `${season} season trade` : "Trade";
}

function tradeWhen(row: SnapshotRow): string {
  const season = numberField(row, "season");
  const week = numberField(row, "week");
  return [season ? `${season} season` : undefined, week ? `Week ${week}` : undefined]
    .filter(Boolean)
    .join(" · ");
}

function booleanEligible(row: SnapshotRow): boolean {
  return row["scoreEligible"] === true;
}
