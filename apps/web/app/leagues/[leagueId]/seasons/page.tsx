import type { Route } from "next";
import { redirect } from "next/navigation";

type SeasonsPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

// Seasons now live inside History (mygm-fixes goal, Phase 5). The per-season hub at
// /seasons/[season] still exists; only the index redirects into the History timeline.
export default async function SeasonsPage({ params }: SeasonsPageProps) {
  const { leagueId } = await params;
  redirect(`/leagues/${leagueId}/history` as Route);
}
