import type { ReactNode } from "react";
import { ManagerLogosProvider } from "@/components/manager-logos-provider";

type LeagueLayoutProps = {
  readonly children: ReactNode;
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

// Wraps every /leagues/[leagueId]/* surface so team emblems can resolve their
// logo by managerKey from a single league-wide directory fetch.
export default async function LeagueLayout({ children, params }: LeagueLayoutProps) {
  const { leagueId } = await params;
  return <ManagerLogosProvider leagueId={leagueId}>{children}</ManagerLogosProvider>;
}
