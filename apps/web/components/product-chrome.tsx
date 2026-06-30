"use client";

import {
  BarChart3,
  BookMarked,
  Home,
  Layers,
  type LucideIcon,
  Medal,
  Newspaper,
  Scale,
  Swords,
  Trophy,
  Wrench
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

type NavItem = {
  readonly label: string;
  readonly href: string;
  readonly icon: LucideIcon;
};

// Casual-friendly three-group IA (next-build goal, Priority 4): a real Home, the
// "My League" reading hubs, and the "Tools" analytics browsers. Managers directory,
// Data Health, Settings, Overview, and Formula are intentionally not in the nav.
const myLeagueItems: readonly NavItem[] = [
  { label: "League News", href: "/news", icon: Newspaper },
  { label: "History", href: "/history", icon: BarChart3 },
  { label: "Rivalries", href: "/rivalries", icon: Swords },
  { label: "Record Book", href: "/record-book", icon: BookMarked },
  { label: "Players", href: "/players", icon: Medal }
];

const toolItems: readonly NavItem[] = [
  { label: "Trade Browser", href: "/trades", icon: Scale },
  { label: "Waiver Browser", href: "/waivers", icon: Layers },
  { label: "GM Rating breakdown", href: "/gms", icon: Trophy }
];

function NavDropdown({
  label,
  items,
  leagueId,
  pathname
}: {
  readonly label: string;
  readonly items: readonly NavItem[];
  readonly leagueId: string;
  readonly pathname: string;
}) {
  const base = `/leagues/${leagueId}`;
  const active = items.some((item) => pathname.startsWith(`${base}${item.href}`));
  return (
    <details className="nav-tools">
      <summary aria-current={active ? "page" : undefined}>
        <Wrench aria-hidden="true" size={15} />
        {label}
      </summary>
      <div className="nav-tools__menu">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = pathname.startsWith(`${base}${item.href}`);
          return (
            <Link
              href={`${base}${item.href}` as Route}
              key={item.label}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon aria-hidden="true" size={15} />
              {item.label}
            </Link>
          );
        })}
      </div>
    </details>
  );
}

export function LeagueNav({ leagueId }: { readonly leagueId: string }) {
  const pathname = usePathname() ?? "";
  const base = `/leagues/${leagueId}`;
  const homeActive = pathname === base || pathname === `${base}/`;
  return (
    <nav className="league-nav" aria-label="League navigation">
      <Link href={base as Route} aria-current={homeActive ? "page" : undefined}>
        <Home aria-hidden="true" size={15} />
        Home
      </Link>
      <NavDropdown
        label="My League"
        items={myLeagueItems}
        leagueId={leagueId}
        pathname={pathname}
      />
      <NavDropdown label="Tools" items={toolItems} leagueId={leagueId} pathname={pathname} />
    </nav>
  );
}

export function ProductHeader({
  eyebrow,
  title,
  leagueId,
  children
}: {
  readonly eyebrow: string;
  readonly title: string;
  readonly leagueId?: string;
  readonly children?: ReactNode;
}) {
  return (
    <header className="product-header">
      <div>
        <p className="product-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {leagueId ? <p className="product-subtitle">Current analytics version</p> : null}
      </div>
      {children}
    </header>
  );
}

export function MetricStrip({
  metrics
}: {
  readonly metrics: readonly {
    readonly label: string;
    readonly value: string;
    readonly detail: string;
  }[];
}) {
  return (
    <dl className="metric-strip">
      {metrics.map((metric) => (
        <div key={metric.label}>
          <dt>{metric.label}</dt>
          <dd className={metric.value.length > 24 ? "is-text" : undefined}>{metric.value}</dd>
          <p>{metric.detail}</p>
        </div>
      ))}
    </dl>
  );
}

export function EvidenceList({
  items
}: {
  readonly items: readonly { readonly label: string; readonly value: string }[];
}) {
  return (
    <dl className="evidence-list">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
