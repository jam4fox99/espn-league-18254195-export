"use client";

import { type CSSProperties, useCallback, useState } from "react";
import { AliasGrid } from "@/components/alias-grid";
import { FranchiseStockChart, RatingRadar } from "@/components/franchise-charts";
import { PlayerImage } from "@/components/player-image";
import { LeagueNav, MetricStrip } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import { TeamEmblem } from "@/components/team-emblem";
import { archetypeColor, selectLogo } from "@/lib/images";
import type {
  DraftCardData,
  DraftPickRef,
  ManagerEra,
  ManagerHubData,
  ManagerSeasonLine,
  RivalryEdge,
  RosterEntry,
  RosterHistoryData
} from "@/lib/product-api";
import { readManagerHub } from "@/lib/product-api";
import { scoreLine } from "@/lib/product-model";
import type { AlphaSession } from "@/lib/session";

type ArchetypeStyle = CSSProperties & { "--arch": string };

type Career = ManagerHubData["career"];
type TradeValue = NonNullable<ManagerHubData["value"]["trade"]>;
type WaiverValue = NonNullable<ManagerHubData["value"]["waiver"]>;

export function FranchiseHub({
  leagueId,
  managerKey
}: {
  readonly leagueId: string;
  readonly managerKey: string;
}) {
  const load = useCallback(
    (session: AlphaSession) => readManagerHub(session, leagueId, managerKey),
    [leagueId, managerKey]
  );

  return (
    <ProductLoader load={load}>
      {(hub) => (
        <section className="product-stack">
          <LeagueNav leagueId={leagueId} />
          <FranchiseHeader hub={hub} />
          <MetricStrip metrics={careerMetrics(hub)} />
          {hub.teamAliases.length > 0 ? (
            <article className="product-panel">
              <p className="section-kicker">Team identities by season</p>
              <AliasGrid
                aliases={hub.teamAliases}
                logoOf={(season) => selectLogo(hub.logo, season)}
              />
            </article>
          ) : null}
          <div className="franchise-grid">
            <article className="product-panel">
              <p className="section-kicker">Rating shape</p>
              <RatingRadar data={radarData(hub)} />
            </article>
            <article className="product-panel">
              <p className="section-kicker">Franchise stock</p>
              <FranchiseStockChart data={stockData(hub.career.seasonLines)} />
            </article>
          </div>
          {hub.career.eras.length > 0 ? <ErasPanel eras={hub.career.eras} /> : null}
          <SeasonTimeline lines={hub.career.seasonLines} logo={hub.logo} />
          <div className="franchise-grid">
            <TradeLedger trade={hub.value.trade} />
            <WaiverLedger waiver={hub.value.waiver} />
          </div>
          {hub.draftCard?.bestPick || hub.draftCard?.worstPick ? (
            <DraftCardPanel card={hub.draftCard} />
          ) : null}
          {hub.rosterHistory ? <RosterHistoryPanel history={hub.rosterHistory} /> : null}
          <RivalrySplit favorite={hub.rivalry.favorite} nemesis={hub.rivalry.nemesis} />
          {hub.caveats.length > 0 ? (
            <p className="muted-note">{[...new Set(hub.caveats)].join(" · ")}</p>
          ) : null}
        </section>
      )}
    </ProductLoader>
  );
}

function FranchiseHeader({ hub }: { readonly hub: ManagerHubData }) {
  const sig = hub.signaturePlayer;
  return (
    <header className="franchise-header">
      <div className="franchise-header__main">
        <TeamEmblem logo={selectLogo(hub.logo)} name={hub.displayName} size={72} />
        <div className="franchise-header__id">
          <p className="product-eyebrow">Franchise hub</p>
          <h1>{hub.displayName}</h1>
          {hub.archetype?.name ? (
            <div className="franchise-archetype">
              <span
                className="franchise-archetype__badge"
                style={{ "--arch": archetypeColor(hub.archetype.name) } as ArchetypeStyle}
              >
                {hub.archetype.name}
              </span>
              {hub.archetype.oneLiner ? (
                <p className="franchise-archetype__line">{hub.archetype.oneLiner}</p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
      {sig ? (
        <div className="gm-hero__sig franchise-header__sig">
          <PlayerImage playerId={sig.playerId} name={sig.name} size={54} priority />
          <span className="gm-hero__sig-meta">
            <span className="gm-hero__sig-k">Signature player</span>
            <span className="gm-hero__sig-name">{sig.name}</span>
            <span className="gm-hero__sig-sub">
              {sig.season ? `${sig.season} · ` : ""}
              {sig.points != null ? `${sig.points.toFixed(1)} pts` : ""}
            </span>
          </span>
        </div>
      ) : null}
    </header>
  );
}

function careerMetrics(hub: ManagerHubData) {
  const career = hub.career;
  return [
    {
      label: "Career GM rating",
      value: scoreLine(hub.careerRating ?? null),
      detail: "Mean of season scores; 2026 excluded."
    },
    {
      label: "All-time record",
      value: recordLine(career),
      detail: `${formatNumber(career.winPct)}% win rate over ${career.seasonsPlayed ?? 0} seasons.`
    },
    {
      label: "Titles",
      value: `${career.titles ?? 0}`,
      detail: `${career.runnerUps ?? 0} runner-up · ${career.playoffAppearances ?? 0} playoff trips.`
    },
    {
      label: "Best / worst finish",
      value: `${ordinal(career.bestFinish)} / ${ordinal(career.worstFinish)}`,
      detail: career.bestFinishSeason ? `Best in ${career.bestFinishSeason}.` : "Final standings."
    }
  ];
}

function ErasPanel({ eras }: { readonly eras: readonly ManagerEra[] }) {
  return (
    <article className="product-panel">
      <p className="section-kicker">Eras</p>
      <ul className="era-list">
        {eras.map((era) => (
          <li key={`${era.kind}-${era.startSeason}`} className={`era-chip era-chip--${era.kind}`}>
            <span className="era-chip__kind">{titleCase(era.kind)}</span>
            <span className="era-chip__span">
              {era.startSeason}
              {era.endSeason !== era.startSeason ? `–${era.endSeason}` : ""}
            </span>
            {era.summary ? <span className="era-chip__summary">{era.summary}</span> : null}
          </li>
        ))}
      </ul>
    </article>
  );
}

function SeasonTimeline({
  lines,
  logo
}: {
  readonly lines: readonly ManagerSeasonLine[];
  readonly logo: ManagerHubData["logo"];
}) {
  const ordered = [...lines].sort((a, b) => b.season - a.season);
  if (ordered.length === 0) {
    return null;
  }
  return (
    <article className="product-panel">
      <p className="section-kicker">Season by season</p>
      <ul className="season-line-list">
        {ordered.map((line) => (
          <li key={line.season} className="season-line">
            <TeamEmblem
              logo={selectLogo(logo, line.season)}
              name={line.teamName ?? `${line.season}`}
              size={26}
            />
            <span className="season-line__year">{line.season}</span>
            <span className="season-line__team">{line.teamName ?? "—"}</span>
            <span className="season-line__record">
              {line.wins ?? 0}-{line.losses ?? 0}
              {line.ties ? `-${line.ties}` : ""}
            </span>
            <span className="season-line__finish">
              {line.isChampion ? (
                <StatusPill tone="success">Champion</StatusPill>
              ) : (
                `${ordinal(line.rankFinal)} place`
              )}
            </span>
            <span className="season-line__rating">{scoreLine(line.ratingScore ?? null)}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function TradeLedger({ trade }: { readonly trade: TradeValue | undefined }) {
  if (!trade) {
    return null;
  }
  return (
    <article className="product-panel">
      <p className="section-kicker">Trade ledger</p>
      <dl className="ledger-stats">
        <div>
          <dt>Net points</dt>
          <dd>{formatSigned(trade.netPoints)}</dd>
        </div>
        <div>
          <dt>Trades</dt>
          <dd>{trade.tradeCount ?? 0}</dd>
        </div>
      </dl>
      {trade.bestTrade?.summary ? (
        <p className="ledger-line">
          <span className="ledger-line__tag ledger-line__tag--good">Best</span>
          {trade.bestTrade.summary}
          {trade.bestTrade.netPoints != null ? ` (${formatSigned(trade.bestTrade.netPoints)})` : ""}
        </p>
      ) : null}
      {trade.worstTrade?.summary ? (
        <p className="ledger-line">
          <span className="ledger-line__tag ledger-line__tag--bad">Worst</span>
          {trade.worstTrade.summary}
          {trade.worstTrade.netPoints != null
            ? ` (${formatSigned(trade.worstTrade.netPoints)})`
            : ""}
        </p>
      ) : null}
      {trade.partners.length > 0 ? (
        <div className="partner-list">
          <p className="section-kicker">Trade partners</p>
          <ul>
            {trade.partners.slice(0, 4).map((partner) => (
              <li key={partner.managerKey ?? partner.displayName}>
                {partner.displayName ?? "Manager"} · {partner.tradeCount ?? 0} deals ·{" "}
                {formatSigned(partner.netPoints)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </article>
  );
}

function WaiverLedger({ waiver }: { readonly waiver: WaiverValue | undefined }) {
  if (!waiver) {
    return null;
  }
  return (
    <article className="product-panel">
      <p className="section-kicker">Waiver ledger</p>
      <dl className="ledger-stats">
        <div>
          <dt>Net points</dt>
          <dd>{formatSigned(waiver.netPoints)}</dd>
        </div>
        <div>
          <dt>Eligible moves</dt>
          <dd>{waiver.eligibleMoves ?? 0}</dd>
        </div>
      </dl>
      {waiver.bestPickup?.summary ? (
        <p className="ledger-line">
          <span className="ledger-line__tag ledger-line__tag--good">Best pickup</span>
          {waiver.bestPickup.summary}
          {waiver.bestPickup.points != null ? ` (+${formatNumber(waiver.bestPickup.points)})` : ""}
        </p>
      ) : null}
      {waiver.worstDrop?.summary ? (
        <p className="ledger-line">
          <span className="ledger-line__tag ledger-line__tag--bad">Worst drop</span>
          {waiver.worstDrop.summary}
          {waiver.worstDrop.points != null ? ` (${formatNumber(waiver.worstDrop.points)})` : ""}
        </p>
      ) : null}
    </article>
  );
}

function draftPickLine(pick: DraftPickRef): string {
  const where =
    pick.round !== undefined
      ? `R${pick.round}, #${pick.overallPick ?? "?"}`
      : pick.overallPick !== undefined
        ? `#${pick.overallPick}`
        : "";
  const surplus = pick.surplus === undefined ? "" : ` · ${formatSigned(pick.surplus)} VOR`;
  return `${pick.playerName ?? "Unknown"}${where ? ` (${where})` : ""}${surplus}`;
}

function DraftCardPanel({ card }: { readonly card: DraftCardData }) {
  return (
    <article className="product-panel">
      <p className="section-kicker">Draft card</p>
      {card.careerSurplus !== undefined ? (
        <dl className="ledger-stats">
          <div>
            <dt>Career draft surplus</dt>
            <dd>{formatSigned(card.careerSurplus)} VOR</dd>
          </div>
        </dl>
      ) : null}
      {card.bestPick ? (
        <p className="ledger-line">
          <span className="ledger-line__tag ledger-line__tag--good">Best pick</span>
          {draftPickLine(card.bestPick)}
        </p>
      ) : null}
      {card.worstPick ? (
        <p className="ledger-line">
          <span className="ledger-line__tag ledger-line__tag--bad">Biggest reach</span>
          {draftPickLine(card.worstPick)}
        </p>
      ) : null}
    </article>
  );
}

function RosterHistoryPanel({ history }: { readonly history: RosterHistoryData }) {
  const [byTotal, setByTotal] = useState(false);
  const lineup = byTotal ? history.allTimeByTotalPoints : history.allTimeLineup;
  if (lineup.length === 0 && history.cornerstones.length === 0) {
    return null;
  }
  return (
    <article className="product-panel roster-history">
      <div className="roster-history__head">
        <p className="section-kicker">All-time roster</p>
        {lineup.length > 0 ? (
          <div className="roster-toggle">
            <button
              type="button"
              aria-pressed={!byTotal}
              className={`roster-toggle__btn${byTotal ? "" : " is-active"}`}
              onClick={() => setByTotal(false)}
            >
              PPG
            </button>
            <button
              type="button"
              aria-pressed={byTotal}
              className={`roster-toggle__btn${byTotal ? " is-active" : ""}`}
              onClick={() => setByTotal(true)}
            >
              Total
            </button>
          </div>
        ) : null}
      </div>
      {lineup.length > 0 ? (
        <ul className="roster-lineup">
          {lineup.map((entry) => (
            <li className="roster-lineup__row" key={`${entry.slot}-${entry.playerId}`}>
              <span className="roster-lineup__slot">{entry.slot || entry.position}</span>
              <PlayerImage playerId={entry.playerId} name={entry.name} size={30} />
              <span className="roster-lineup__name">{entry.name}</span>
              <span className="roster-lineup__meta">
                {entry.position}
                {entry.season ? ` · ${entry.season}` : ""}
              </span>
              <span className="roster-lineup__stat">{rosterStat(entry, byTotal)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {history.cornerstones.length > 0 ? (
        <div className="roster-cornerstones">
          <p className="section-kicker">Cornerstones</p>
          <ul>
            {history.cornerstones.slice(0, 6).map((stone) => (
              <li className="roster-cornerstone" key={stone.playerId}>
                <span className="roster-cornerstone__name">{stone.name}</span>
                <span className="roster-cornerstone__weeks">{stone.weeksStarted} starts</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {history.bestSeason ? (
        <p className="muted-note">
          Best season: {history.bestSeason.season} · {formatNumber(history.bestSeason.pointsFor)}{" "}
          points for
        </p>
      ) : null}
    </article>
  );
}

function rosterStat(entry: RosterEntry, byTotal: boolean): string {
  return byTotal ? `${formatNumber(entry.totalPoints)} pts` : `${formatNumber(entry.ppg)} ppg`;
}

function RivalrySplit({
  favorite,
  nemesis
}: {
  readonly favorite: RivalryEdge | null | undefined;
  readonly nemesis: RivalryEdge | null | undefined;
}) {
  if (!favorite && !nemesis) {
    return null;
  }
  return (
    <div className="franchise-grid">
      {favorite ? <RivalryCard edge={favorite} tone="favorite" label="Favorite opponent" /> : null}
      {nemesis ? <RivalryCard edge={nemesis} tone="nemesis" label="Nemesis" /> : null}
    </div>
  );
}

function RivalryCard({
  edge,
  tone,
  label
}: {
  readonly edge: RivalryEdge;
  readonly tone: "favorite" | "nemesis";
  readonly label: string;
}) {
  return (
    <article className={`product-panel rivalry-card rivalry-card--${tone}`}>
      <p className="section-kicker">{label}</p>
      <h3 className="rivalry-card__name">{edge.opponentDisplayName ?? "Opponent"}</h3>
      <p className="rivalry-card__record">
        {edge.wins ?? 0}-{edge.losses ?? 0}
        {edge.ties ? `-${edge.ties}` : ""} · {formatNumber(edge.winPct)}% · {edge.games ?? 0} games
      </p>
      {edge.currentStreak ? (
        <p className="muted-note">Current streak: {edge.currentStreak}</p>
      ) : null}
    </article>
  );
}

function radarData(hub: ManagerHubData): { component: string; value: number }[] {
  return Object.entries(hub.ratingComponents).map(([key, component]) => ({
    component: typeof component.label === "string" ? component.label : key,
    value: Number(component.value ?? component.score ?? 0)
  }));
}

function stockData(
  lines: readonly ManagerSeasonLine[]
): { season: number; rating: number | null }[] {
  return [...lines]
    .sort((a, b) => a.season - b.season)
    .map((line) => ({ season: line.season, rating: line.ratingScore ?? null }));
}

function recordLine(career: Career): string {
  return `${career.wins ?? 0}-${career.losses ?? 0}${career.ties ? `-${career.ties}` : ""}`;
}

function ordinal(rank: number | undefined): string {
  if (rank === undefined) {
    return "—";
  }
  const mod100 = rank % 100;
  if (mod100 >= 11 && mod100 <= 13) {
    return `${rank}th`;
  }
  const suffix = ["th", "st", "nd", "rd"][rank % 10] ?? "th";
  return `${rank}${suffix}`;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return value.toFixed(1);
}

function formatSigned(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const rounded = value.toFixed(1);
  return value > 0 ? `+${rounded}` : rounded;
}

function titleCase(value: string): string {
  return value.length === 0 ? value : `${value[0]?.toUpperCase() ?? ""}${value.slice(1)}`;
}
