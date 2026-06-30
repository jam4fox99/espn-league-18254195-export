"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { selectLogo } from "@/lib/images";
import { type ManagerLogoData, readManagerDirectory } from "@/lib/product-api";
import { ensureAlphaTestSession } from "@/lib/session";

/** Resolve a manager's emblem URL by managerKey (+ optional season). Null → monogram. */
export type ManagerLogoResolver = (
  managerKey?: string | null,
  season?: number | null
) => string | null;

const ManagerLogosContext = createContext<ManagerLogoResolver>(() => null);

/**
 * Resolver that maps a `managerKey` (+ optional season) to its team emblem URL.
 * Available to every league surface so emblems render league-wide — not just on
 * the leaderboard. Falls back to `null` (→ monogram) for unknown keys or before
 * the directory loads, so there is never a broken image. (§7c)
 */
export function useManagerLogo(): ManagerLogoResolver {
  return useContext(ManagerLogosContext);
}

/**
 * Loads the league's manager directory once (the single source of per-season
 * team logos, keyed by owner GUID) and shares a `managerKey → logo` resolver
 * with all descendant surfaces: trades, waivers, rivalries, head-to-head,
 * history, and seasons. Surfaces that already carry row-level logos keep using
 * them; this fills the gap everywhere else.
 */
export function ManagerLogosProvider({
  leagueId,
  children
}: {
  readonly leagueId: string;
  readonly children: ReactNode;
}) {
  const [logos, setLogos] = useState<ReadonlyMap<string, ManagerLogoData>>(new Map());

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const session = ensureAlphaTestSession(window.localStorage);
        const directory = await readManagerDirectory(session, leagueId);
        if (!active) {
          return;
        }
        const next = new Map<string, ManagerLogoData>();
        for (const manager of directory.managers) {
          if (manager.managerKey && manager.logo) {
            next.set(manager.managerKey, manager.logo);
          }
        }
        setLogos(next);
      } catch {
        // Leave the map empty: emblems fall back to monograms (no regression).
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [leagueId]);

  const resolver = useCallback<ManagerLogoResolver>(
    (managerKey, season) => {
      if (!managerKey) {
        return null;
      }
      const logo = logos.get(managerKey);
      return logo ? selectLogo(logo, season ?? null) : null;
    },
    [logos]
  );

  return <ManagerLogosContext.Provider value={resolver}>{children}</ManagerLogosContext.Provider>;
}
