"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const demoLeagueId = "11111111-1111-4111-8111-111111111111";

const topbarLinks: readonly {
  readonly label: string;
  readonly href: Route;
  readonly match: (pathname: string) => boolean;
}[] = [
  {
    label: "History",
    href: `/leagues/${demoLeagueId}/history` as Route,
    match: (pathname) => pathname.includes("/history")
  },
  {
    label: "Managers",
    href: `/leagues/${demoLeagueId}/gms` as Route,
    match: (pathname) => pathname === "/" || pathname.includes("/gms")
  },
  {
    label: "Seasons",
    href: `/leagues/${demoLeagueId}/history` as Route,
    match: (pathname) => pathname.includes("/seasons")
  },
  {
    label: "Rivalries",
    href: `/leagues/${demoLeagueId}/rivalries` as Route,
    match: (pathname) => pathname.includes("/rivalries")
  },
  {
    label: "Record Book",
    href: `/leagues/${demoLeagueId}/record-book` as Route,
    match: (pathname) => pathname.includes("/record-book") || pathname.includes("/records")
  },
  {
    label: "Players",
    href: `/leagues/${demoLeagueId}/players` as Route,
    match: (pathname) => pathname.includes("/players")
  },
  {
    label: "Tools",
    href: "/connect",
    match: (pathname) => pathname.startsWith("/connect") || pathname.includes("/import-runs")
  }
];

export function AppFrame({ children }: { readonly children: ReactNode }) {
  const pathname = usePathname() ?? "/";

  return (
    <div className="app-frame">
      <header className="topbar">
        <div className="topbar__left">
          <Link className="brand-lockup" href="/" aria-label="MyGM home">
            <span>GM</span>
          </Link>
          <div className="topbar-keys" aria-hidden="true">
            <span>Q</span>
            <span>E</span>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          {topbarLinks.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              aria-current={item.match(pathname) ? "page" : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="page-shell">{children}</main>
    </div>
  );
}
