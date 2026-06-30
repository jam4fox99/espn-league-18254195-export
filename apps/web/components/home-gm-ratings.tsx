"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { SegmentedMeter } from "@/components/rating-visuals";

type HomeGm = {
  readonly rank: number;
  readonly name: string;
  readonly team: string;
  readonly rating: number;
  readonly titles: number;
  readonly winPct: number;
  readonly tier: string;
  readonly seasons: number;
  readonly record: string;
  readonly bestFinish: string;
  readonly attributes: readonly {
    readonly label: string;
    readonly value: number;
  }[];
};

const homeGms: readonly HomeGm[] = [
  {
    rank: 1,
    name: "Marcus Vale",
    team: "Vale Dynasty",
    rating: 92.4,
    titles: 4,
    winPct: 71.2,
    tier: "S TIER GM",
    seasons: 15,
    record: "256-104",
    bestFinish: "CHAMP x4",
    attributes: [
      { label: "OFFENSE", value: 95 },
      { label: "DEFENSE", value: 98 },
      { label: "SCOUTING", value: 99 },
      { label: "DEVELOPMENT", value: 99 },
      { label: "CHEMISTRY", value: 86 }
    ]
  },
  {
    rank: 2,
    name: "Theo Brandt",
    team: "Iron Wolves",
    rating: 89.1,
    titles: 3,
    winPct: 68.5,
    tier: "A TIER GM",
    seasons: 14,
    record: "231-106",
    bestFinish: "CHAMP x3",
    attributes: [
      { label: "OFFENSE", value: 92 },
      { label: "DEFENSE", value: 91 },
      { label: "SCOUTING", value: 94 },
      { label: "DEVELOPMENT", value: 88 },
      { label: "CHEMISTRY", value: 84 }
    ]
  },
  {
    rank: 3,
    name: "Dante Cross",
    team: "Midnight Reign",
    rating: 86.7,
    titles: 2,
    winPct: 64.0,
    tier: "A TIER GM",
    seasons: 13,
    record: "205-115",
    bestFinish: "CHAMP x2",
    attributes: [
      { label: "OFFENSE", value: 89 },
      { label: "DEFENSE", value: 87 },
      { label: "SCOUTING", value: 93 },
      { label: "DEVELOPMENT", value: 86 },
      { label: "CHEMISTRY", value: 79 }
    ]
  },
  {
    rank: 4,
    name: "Silas Pope",
    team: "Cathedral Kings",
    rating: 84.3,
    titles: 2,
    winPct: 61.8,
    tier: "B TIER GM",
    seasons: 12,
    record: "188-116",
    bestFinish: "CHAMP x2",
    attributes: [
      { label: "OFFENSE", value: 84 },
      { label: "DEFENSE", value: 88 },
      { label: "SCOUTING", value: 82 },
      { label: "DEVELOPMENT", value: 90 },
      { label: "CHEMISTRY", value: 77 }
    ]
  },
  {
    rank: 5,
    name: "Roman Vega",
    team: "Vega United",
    rating: 81.9,
    titles: 1,
    winPct: 59.4,
    tier: "B TIER GM",
    seasons: 11,
    record: "171-117",
    bestFinish: "CHAMP x1",
    attributes: [
      { label: "OFFENSE", value: 82 },
      { label: "DEFENSE", value: 80 },
      { label: "SCOUTING", value: 85 },
      { label: "DEVELOPMENT", value: 79 },
      { label: "CHEMISTRY", value: 83 }
    ]
  },
  {
    rank: 6,
    name: "Cole Mercer",
    team: "Mercer's Marauders",
    rating: 78.5,
    titles: 1,
    winPct: 57.1,
    tier: "B TIER GM",
    seasons: 10,
    record: "154-116",
    bestFinish: "FINALIST",
    attributes: [
      { label: "OFFENSE", value: 76 },
      { label: "DEFENSE", value: 83 },
      { label: "SCOUTING", value: 81 },
      { label: "DEVELOPMENT", value: 75 },
      { label: "CHEMISTRY", value: 78 }
    ]
  },
  {
    rank: 7,
    name: "Quinn Ashford",
    team: "Ashford Athletic",
    rating: 75.2,
    titles: 1,
    winPct: 54.6,
    tier: "C TIER GM",
    seasons: 9,
    record: "136-113",
    bestFinish: "CHAMP x1",
    attributes: [
      { label: "OFFENSE", value: 74 },
      { label: "DEFENSE", value: 77 },
      { label: "SCOUTING", value: 72 },
      { label: "DEVELOPMENT", value: 73 },
      { label: "CHEMISTRY", value: 80 }
    ]
  },
  {
    rank: 8,
    name: "Felix Hart",
    team: "Hart Breakers",
    rating: 71.8,
    titles: 0,
    winPct: 51.0,
    tier: "C TIER GM",
    seasons: 8,
    record: "118-114",
    bestFinish: "SEMIS",
    attributes: [
      { label: "OFFENSE", value: 70 },
      { label: "DEFENSE", value: 73 },
      { label: "SCOUTING", value: 69 },
      { label: "DEVELOPMENT", value: 74 },
      { label: "CHEMISTRY", value: 72 }
    ]
  },
  {
    rank: 9,
    name: "Ivan Korso",
    team: "Korso Collective",
    rating: 68.4,
    titles: 0,
    winPct: 47.3,
    tier: "D TIER GM",
    seasons: 7,
    record: "96-107",
    bestFinish: "PLAYOFFS",
    attributes: [
      { label: "OFFENSE", value: 66 },
      { label: "DEFENSE", value: 70 },
      { label: "SCOUTING", value: 68 },
      { label: "DEVELOPMENT", value: 64 },
      { label: "CHEMISTRY", value: 71 }
    ]
  },
  {
    rank: 10,
    name: "Nash Powell",
    team: "Powell Pack",
    rating: 64.0,
    titles: 0,
    winPct: 43.8,
    tier: "D TIER GM",
    seasons: 6,
    record: "74-95",
    bestFinish: "PLAYOFFS",
    attributes: [
      { label: "OFFENSE", value: 62 },
      { label: "DEFENSE", value: 64 },
      { label: "SCOUTING", value: 67 },
      { label: "DEVELOPMENT", value: 61 },
      { label: "CHEMISTRY", value: 66 }
    ]
  },
  {
    rank: 11,
    name: "Owen Frost",
    team: "Frostbite FC",
    rating: 60.6,
    titles: 0,
    winPct: 39.5,
    tier: "D TIER GM",
    seasons: 5,
    record: "57-88",
    bestFinish: "WILD CARD",
    attributes: [
      { label: "OFFENSE", value: 58 },
      { label: "DEFENSE", value: 63 },
      { label: "SCOUTING", value: 60 },
      { label: "DEVELOPMENT", value: 59 },
      { label: "CHEMISTRY", value: 62 }
    ]
  },
  {
    rank: 12,
    name: "Drew Salas",
    team: "Salas Syndicate",
    rating: 55.1,
    titles: 0,
    winPct: 33.2,
    tier: "D TIER GM",
    seasons: 4,
    record: "39-78",
    bestFinish: "REBUILD",
    attributes: [
      { label: "OFFENSE", value: 53 },
      { label: "DEFENSE", value: 57 },
      { label: "SCOUTING", value: 56 },
      { label: "DEVELOPMENT", value: 52 },
      { label: "CHEMISTRY", value: 55 }
    ]
  }
];

export function HomeGmRatings() {
  const [selectedRank, setSelectedRank] = useState(1);
  const selected = useMemo(
    () => homeGms.find((gm) => gm.rank === selectedRank) ?? homeGms[0],
    [selectedRank]
  );

  return (
    <section className="home-gm-page" aria-labelledby="home-title">
      <header className="home-gm-hero">
        <div>
          <p className="home-gm-eyebrow">Franchise Directory</p>
          <h1 id="home-title">GM Ratings</h1>
        </div>
        <div className="home-gm-count" aria-label={`${homeGms.length} GMs ranked`}>
          <strong>{homeGms.length}</strong>
          <span>GMs Ranked</span>
        </div>
      </header>

      <div className="home-gm-layout">
        <section className="home-gm-panel home-gm-standings" aria-labelledby="standings-title">
          <PanelTitle id="standings-title" label="League Standings" meta="Sorted by GM Rating" />
          <div className="home-gm-table-head" aria-hidden="true">
            <span>#</span>
            <span>Manager</span>
            <span>GM Rating</span>
            <span>Titles</span>
            <span>Win %</span>
          </div>
          <ol className="home-gm-list">
            {homeGms.slice(0, 7).map((gm) => (
              <li key={gm.rank}>
                <button
                  type="button"
                  className="home-gm-row"
                  data-active={gm.rank === selected.rank ? "true" : undefined}
                  onClick={() => setSelectedRank(gm.rank)}
                  aria-label={`Select ${gm.name}`}
                >
                  <span className="home-gm-row__rank">{String(gm.rank).padStart(2, "0")}</span>
                  <RatingRing value={gm.rating} size="small" />
                  <span className="home-gm-row__manager">
                    <strong>{gm.name}</strong>
                    <small>{gm.team}</small>
                  </span>
                  <span className="home-gm-row__rating">
                    <strong>{gm.rating.toFixed(1)}</strong>
                    <small>/ 100</small>
                  </span>
                  <span className="home-gm-row__titles">
                    <strong>{gm.titles}</strong>
                    <TitleMarks count={gm.titles} />
                  </span>
                  <span className="home-gm-row__win">
                    <strong>{gm.winPct.toFixed(1)}%</strong>
                    <small>Win %</small>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>

        <aside className="home-gm-panel home-gm-card" aria-labelledby="card-title">
          <PanelTitle
            id="card-title"
            label="GM Card"
            meta={`Rank ${String(selected.rank).padStart(2, "0")}`}
          />
          <div className="home-gm-card__body">
            <div className="home-gm-card__main">
              <RatingRing value={selected.rating} size="large" />
              <div className="home-gm-card__id">
                <span className="home-gm-tier">{selected.tier}</span>
                <h2>{selected.name}</h2>
                <p>{selected.team}</p>
                <div className="home-gm-scoreline">
                  <strong>{selected.rating.toFixed(1)}</strong>
                  <span>GM Rating / 100</span>
                </div>
              </div>
              <div className="home-gm-card__titles">
                <span>Titles</span>
                <strong>{selected.titles}</strong>
                <small>Won</small>
              </div>
            </div>

            <div className="home-gm-winbar" style={{ "--win-pct": selected.winPct }}>
              <span>Win %</span>
              <strong>{selected.winPct.toFixed(1)}%</strong>
              <div aria-hidden="true">
                <span />
              </div>
            </div>

            <section className="home-gm-index" aria-labelledby="index-title">
              <h3 id="index-title">Performance Index</h3>
              <div className="home-gm-index__rows">
                {selected.attributes.map((attribute) => (
                  <div className="home-gm-index__row" key={attribute.label}>
                    <span>{attribute.label}</span>
                    <SegmentedMeter value={attribute.value} cells={12} stagger />
                    <strong>{attribute.value}</strong>
                  </div>
                ))}
              </div>
            </section>

            <dl className="home-gm-card__stats">
              <div>
                <dt>Seasons</dt>
                <dd>{selected.seasons}</dd>
              </div>
              <div>
                <dt>Record</dt>
                <dd>{selected.record}</dd>
              </div>
              <div>
                <dt>Best Finish</dt>
                <dd>{selected.bestFinish}</dd>
              </div>
            </dl>

            <Link
              className="home-gm-cta"
              href="/leagues/11111111-1111-4111-8111-111111111111/gms"
            >
              View Full Card
              <span aria-hidden="true">▸▸</span>
            </Link>
          </div>
        </aside>
      </div>

      <footer className="home-gm-footer" aria-label="Reference controls and tiers">
        <div className="home-gm-controls" aria-hidden="true">
          <span>
            <kbd>↑↓</kbd>
            Navigate
          </span>
          <span>
            <kbd>↵</kbd>
            Select GM
          </span>
          <span>
            <kbd>Esc</kbd>
            Back
          </span>
        </div>
        <div className="home-gm-legend" aria-label="Rating tier legend">
          <span>Rating Tier</span>
          {["S", "A", "B", "C", "D"].map((tier) => (
            <span className="home-gm-legend__item" data-tier={tier} key={tier}>
              {tier}
            </span>
          ))}
        </div>
      </footer>
    </section>
  );
}

function PanelTitle({
  id,
  label,
  meta
}: {
  readonly id: string;
  readonly label: string;
  readonly meta: string;
}) {
  return (
    <header className="home-gm-panel-title">
      <h2 id={id}>
        <span aria-hidden="true" />
        {label}
      </h2>
      <span>{meta}</span>
    </header>
  );
}

function RatingRing({ value, size }: { readonly value: number; readonly size: "small" | "large" }) {
  const dimension = size === "large" ? 120 : 52;
  const stroke = size === "large" ? 9 : 5;
  const radius = (dimension - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(100, value)) / 100);

  return (
    <span
      className={`home-rating-ring home-rating-ring--${size}`}
      style={
        {
          "--ring-size": `${dimension}px`,
          "--ring-stroke": stroke,
          "--ring-dash": circumference,
          "--ring-offset": offset,
          "--ring-color": ringColor(value)
        } as React.CSSProperties
      }
      aria-label={`${Math.round(value)} overall rating`}
    >
      <svg width={dimension} height={dimension} viewBox={`0 0 ${dimension} ${dimension}`}>
        <circle
          cx={dimension / 2}
          cy={dimension / 2}
          r={radius}
          fill="none"
          stroke="rgba(120,150,205,.16)"
          strokeWidth={stroke}
        />
        <circle
          cx={dimension / 2}
          cy={dimension / 2}
          r={radius}
          fill="none"
          stroke="var(--ring-color)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${dimension / 2} ${dimension / 2})`}
        />
      </svg>
      <span>
        {size === "large" ? <small>OVR</small> : null}
        {Math.round(value)}
      </span>
    </span>
  );
}

function TitleMarks({ count }: { readonly count: number }) {
  if (count <= 0) {
    return <span className="home-gm-title-marks" aria-label="No titles" />;
  }

  return (
    <span className="home-gm-title-marks" aria-label={`${count} titles`}>
      {Array.from({ length: count }, (_, index) => (
        <span key={index} />
      ))}
    </span>
  );
}

function ringColor(value: number) {
  if (value >= 86) {
    return "var(--yellow)";
  }
  if (value >= 72) {
    return "var(--tier-elite)";
  }
  if (value >= 60) {
    return "var(--blue)";
  }
  return "var(--status-error)";
}
