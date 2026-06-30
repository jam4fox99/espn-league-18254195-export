import type { ReactNode } from "react";

export type InsightTone = "neutral" | "success" | "warning" | "info";

export type InsightMetric = {
  readonly label: string;
  readonly value: string;
  readonly detail: string;
  readonly tone?: InsightTone;
};

export type ProgressMetric = {
  readonly label: string;
  readonly value: number;
  readonly max: number;
  readonly detail: string;
};

export type ActionLink = {
  readonly href: string;
  readonly label: string;
  readonly detail: string;
};

export function InsightDeck({ items }: { readonly items: readonly InsightMetric[] }) {
  return (
    <section className="insight-deck" aria-label="Key evidence">
      {items.map((item) => (
        <article className={`insight-card ${item.tone ?? "neutral"}`} key={item.label}>
          <p className="insight-label">{item.label}</p>
          <strong>{item.value}</strong>
          <p>{item.detail}</p>
        </article>
      ))}
    </section>
  );
}

export function ProgressList({ rows }: { readonly rows: readonly ProgressMetric[] }) {
  return (
    <div className="progress-list">
      {rows.map((row) => (
        <div className="progress-row" key={row.label}>
          <div>
            <span>{row.label}</span>
            <strong>
              {formatNumber(row.value)} / {formatNumber(row.max)}
            </strong>
          </div>
          <meter max={row.max} min={0} value={row.value}>
            {row.value}
          </meter>
          <p>{row.detail}</p>
        </div>
      ))}
    </div>
  );
}

export function Workbench({
  title,
  intro,
  children,
  aside
}: {
  readonly title: string;
  readonly intro: string;
  readonly children: ReactNode;
  readonly aside: ReactNode;
}) {
  return (
    <section className="split-workbench">
      <div>
        <p className="section-kicker">Review surface</p>
        <h2>{title}</h2>
        <p>{intro}</p>
        {children}
      </div>
      <aside>{aside}</aside>
    </section>
  );
}

export function ActionGrid({ items }: { readonly items: readonly ActionLink[] }) {
  return (
    <div className="action-grid">
      {items.map((item) => (
        <a className="action-card" href={item.href} key={item.href}>
          <strong>{item.label}</strong>
          <span>{item.detail}</span>
        </a>
      ))}
    </div>
  );
}

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "Pending" : value.toLocaleString("en-US");
}
