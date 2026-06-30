"use client";

import type { CSSProperties } from "react";
import { useCallback } from "react";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { PlayerChip } from "@/components/player-image";
import { LeagueNav, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { TeamEmblem } from "@/components/team-emblem";
import { recordTone, selectLogo } from "@/lib/images";
import type { RecordBookRow } from "@/lib/product-api";
import { readRecordBook } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

type RecordTone = "best" | "worst" | "neutral";

type CategoryMeta = {
  readonly group: string;
  readonly unit: string;
  /** Drives the value color + card accent: best = green, worst = red. */
  readonly tone: RecordTone;
};

// Curated grouping of the snapshot's superlative records into themed sections.
const CATEGORY_META: Record<string, CategoryMeta> = {
  most_career_points: { group: "Career", unit: "pts", tone: "best" },
  highest_career_ppg: { group: "Career", unit: "PPG", tone: "best" },
  highest_weekly_score: { group: "Scoring", unit: "pts", tone: "best" },
  lowest_weekly_score: { group: "Scoring", unit: "pts", tone: "worst" },
  most_season_points: { group: "Scoring", unit: "pts", tone: "best" },
  closest_matchup: { group: "Matchups", unit: "margin", tone: "neutral" },
  largest_matchup: { group: "Matchups", unit: "margin", tone: "best" },
  best_season_record: { group: "Seasons", unit: "", tone: "best" },
  worst_season_record: { group: "Seasons", unit: "", tone: "worst" },
  draft_steal: { group: "Draft", unit: "", tone: "best" },
  draft_bust: { group: "Draft", unit: "", tone: "worst" },
  best_trade: { group: "Trades & waivers", unit: "pts", tone: "best" },
  worst_trade: { group: "Trades & waivers", unit: "pts", tone: "worst" },
  waiver_value_leader: { group: "Trades & waivers", unit: "pts", tone: "best" },
  best_pickup: { group: "Trades & waivers", unit: "pts", tone: "best" },
  bench_points_leader: { group: "Lineups", unit: "pts", tone: "worst" },
  lineup_efficiency_leader: { group: "Lineups", unit: "%", tone: "best" }
};

const GROUP_ORDER = [
  "Career",
  "Scoring",
  "Matchups",
  "Seasons",
  "Draft",
  "Trades & waivers",
  "Lineups"
];

export function RecordBook({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback(
    (session: AlphaSession) => readRecordBook(session, leagueId),
    [leagueId]
  );

  return (
    <ProductLoader load={load}>
      {(data) => {
        const groups = groupRecords(data.rows);
        return (
          <section className="product-stack">
            <LeagueNav leagueId={leagueId} />
            <ProductHeader eyebrow="Record book" title="League record book" />
            {data.rows.length === 0 ? (
              <p className="muted-note">No records are available for this snapshot yet.</p>
            ) : (
              <p className="muted-note">
                Every entry is the single best (or worst) mark in the league archive, with the
                manager, team, and season that set it.
              </p>
            )}
            {groups.map((group) => (
              <article key={group.name} className="product-panel">
                <p className="section-kicker">{group.name}</p>
                <div className="record-grid">
                  {group.rows.map((row) => (
                    <RecordCard key={row.recordId ?? row.label} row={row} />
                  ))}
                </div>
              </article>
            ))}
          </section>
        );
      }}
    </ProductLoader>
  );
}

function RecordCard({ row }: { readonly row: RecordBookRow }) {
  const logoFor = useManagerLogo();
  const meta = CATEGORY_META[row.category];
  const tone = meta?.tone ?? "neutral";
  const hasPlayer = row.playerId != null || Boolean(row.playerName);
  const holderLogo = logoFor(row.managerKey, row.season) ?? selectLogo(row.logo, row.season);
  const accent = tone === "neutral" ? undefined : recordTone(row.value, tone);
  return (
    <div
      className={`record-card record-card--${tone}`}
      style={accent ? ({ "--rec-accent": accent } as CSSProperties) : undefined}
    >
      <p className="record-card__label">{row.label}</p>
      <p className="record-card__value" style={accent ? { color: accent } : undefined}>
        {formatValue(row.value)}
        {meta?.unit ? <span className="record-card__unit">{meta.unit}</span> : null}
      </p>
      {hasPlayer ? (
        <PlayerChip
          playerId={row.playerId}
          name={row.playerName ?? "Player"}
          teamAbbr={row.proTeamAbbrev}
          isDST={row.isDST}
          size={30}
        />
      ) : null}
      <p className="record-card__holder">
        {holderLogo ? (
          <TeamEmblem
            logo={holderLogo}
            name={row.teamName ?? row.managerName ?? "Manager"}
            size={18}
          />
        ) : null}
        {holderLine(row)}
      </p>
      {row.detail ? <p className="record-card__detail">{row.detail}</p> : null}
    </div>
  );
}

function holderLine(row: RecordBookRow): string {
  const parts = [row.managerName, row.teamName].filter((part): part is string => Boolean(part));
  const who = parts.join(" · ");
  if (row.season) {
    return who ? `${who} · ${row.season}` : `${row.season}`;
  }
  return who || "Unattributed";
}

function formatValue(value: string | number): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  }
  return value;
}

function groupRecords(
  rows: readonly RecordBookRow[]
): readonly { readonly name: string; readonly rows: readonly RecordBookRow[] }[] {
  const byGroup = new Map<string, RecordBookRow[]>();
  for (const row of rows) {
    const group = CATEGORY_META[row.category]?.group ?? "Other";
    const bucket = byGroup.get(group) ?? [];
    bucket.push(row);
    byGroup.set(group, bucket);
  }
  const ordered = [...GROUP_ORDER, "Other"];
  return ordered
    .filter((name) => byGroup.has(name))
    .map((name) => ({ name, rows: byGroup.get(name) ?? [] }));
}
