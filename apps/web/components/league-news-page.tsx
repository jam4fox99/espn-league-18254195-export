"use client";

import {
  Flame,
  Layers,
  type LucideIcon,
  Newspaper,
  Scale,
  Sparkles,
  TrendingDown,
  Trophy
} from "lucide-react";
import { useCallback } from "react";
import { LeagueNav, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import type {
  LeagueNewsData,
  LeagueNewsItem,
  TeamStrength,
  WaiverSuggestionRow
} from "@/lib/product-api";
import { readLeagueNews } from "@/lib/product-api";
import type { AlphaSession } from "@/lib/session";

type NewsTone = "gold" | "green" | "blue" | "neutral";

/** Per-type icon + tone, mirroring the home-page activity feed so the two
 *  surfaces read consistently and the 2-column card grid has its icon child. */
const TYPE_META: Record<string, { label: string; tone: NewsTone; icon: LucideIcon }> = {
  champion: { label: "Champion", tone: "gold", icon: Trophy },
  trade: { label: "Trade", tone: "blue", icon: Scale },
  waiver: { label: "Waiver wire", tone: "green", icon: Layers },
  draftSteal: { label: "Draft steal", tone: "green", icon: Sparkles },
  draftBust: { label: "Draft bust", tone: "neutral", icon: TrendingDown },
  performance: { label: "Top performance", tone: "gold", icon: Flame }
};

const DEFAULT_META = { label: "Update", tone: "neutral", icon: Newspaper } as const;

export function LeagueNewsPage({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback(
    (session: AlphaSession) => readLeagueNews(session, leagueId),
    [leagueId]
  );

  return (
    <ProductLoader load={load}>
      {(news: LeagueNewsData) => (
        <section className="product-stack">
          <LeagueNav leagueId={leagueId} />
          <ProductHeader eyebrow="League news" title={`What's happening — ${news.season}`}>
            <StatusPill tone="info">Latest season</StatusPill>
          </ProductHeader>
          {news.items.length === 0 ? (
            <p className="muted-note">No league activity is available for this snapshot yet.</p>
          ) : (
            <div className="news-layout">
              <article className="product-panel">
                <h2>Headlines</h2>
                <ul className="news-feed">
                  {news.items.map((item) => (
                    <NewsCard key={item.id} item={item} />
                  ))}
                </ul>
              </article>
              <aside className="news-side">
                <TeamStrengthPanel rows={news.teamStrength} />
                <WaiverSuggestionsPanel rows={news.waiverSuggestions} />
              </aside>
            </div>
          )}
        </section>
      )}
    </ProductLoader>
  );
}

function NewsCard({ item }: { readonly item: LeagueNewsItem }) {
  const meta = TYPE_META[item.type] ?? DEFAULT_META;
  const kind = TYPE_META[item.type]?.label ?? item.type;
  const Icon = meta.icon;
  const grades = item.grades ? Object.entries(item.grades) : [];
  return (
    <li className={`news-item news-item--${meta.tone}`}>
      <span className="news-item__icon" aria-hidden="true">
        <Icon size={15} />
      </span>
      <span className="news-item__body">
        <span className="news-item__head">
          <span className="news-item__kind">{kind}</span>
          {item.displayName ? <span className="news-item__season">{item.displayName}</span> : null}
        </span>
        <span className="news-item__text">{item.headline}</span>
        <span className="news-item__detail">{item.detail}</span>
        {grades.length > 0 ? (
          <span className="news-grades">
            {grades.map(([manager, grade]) => (
              <span className="grade" key={manager} data-grade={grade} title={`Grade ${grade}`}>
                {grade}
              </span>
            ))}
          </span>
        ) : null}
        {item.veto ? <VetoBadge percent={item.veto.percent} band={item.veto.band} /> : null}
        {item.contenders && item.contenders.length > 0 ? (
          <span className="news-contenders">
            {item.contenders
              .filter((entry) => entry.displayName !== undefined)
              .map((entry) => (
                <span
                  className="news-contender"
                  key={`${item.id}-${entry.week ?? "w"}-${entry.displayName}`}
                >
                  {entry.displayName}
                  {entry.points === undefined ? null : ` · ${entry.points.toFixed(1)}`}
                </span>
              ))}
          </span>
        ) : null}
      </span>
    </li>
  );
}

function VetoBadge({ percent, band }: { readonly percent: number; readonly band: string }) {
  const tone = band === "Collusion risk" ? "danger" : band === "Lean veto" ? "warn" : "ok";
  return (
    <span className={`veto-badge veto-badge--${tone}`}>
      Veto risk {Math.round(percent)}% · {band}
    </span>
  );
}

function TeamStrengthPanel({ rows }: { readonly rows: readonly TeamStrength[] }) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <article className="product-panel">
      <h2>Team strengths &amp; weaknesses</h2>
      <ul className="strength-list">
        {rows.map((row) => (
          <li className="strength-row" key={row.managerKey}>
            <span className="strength-row__name">{row.displayName}</span>
            <span className="strength-row__tags">
              {row.strongestPosition ? (
                <span className="pos-tag pos-tag--strong">Strong {row.strongestPosition}</span>
              ) : null}
              {row.weakestPosition ? (
                <span className="pos-tag pos-tag--weak">Weak {row.weakestPosition}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function WaiverSuggestionsPanel({ rows }: { readonly rows: readonly WaiverSuggestionRow[] }) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <article className="product-panel">
      <h2>Waiver targets</h2>
      <p className="muted-note">
        Best available free agents at each team's weak spots, by recent form.
      </p>
      <ul className="suggestion-list">
        {rows.map((row) => (
          <li className="suggestion-row" key={row.managerKey}>
            <span className="suggestion-row__name">{row.displayName}</span>
            <span className="suggestion-row__items">
              {row.suggestions.slice(0, 4).map((suggestion) => (
                <span
                  className="suggestion-chip"
                  key={`${row.managerKey}-${suggestion.position}-${suggestion.name}`}
                >
                  <span className="suggestion-chip__pos">{suggestion.position}</span>
                  {suggestion.name}
                  <span className="suggestion-chip__pts">
                    {suggestion.trailingPoints.toFixed(0)}
                  </span>
                </span>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}
