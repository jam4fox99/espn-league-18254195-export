import type { Route } from "next";
import { redirect } from "next/navigation";

type HeadToHeadRouteProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

// Head-to-Head is now folded into Rivalries (mygm-fixes goal, Phase 5): the all-play
// matrix carries the per-pair record, so this route redirects there.
export default async function HeadToHeadRoute({ params }: HeadToHeadRouteProps) {
  const { leagueId } = await params;
  redirect(`/leagues/${leagueId}/rivalries` as Route);
}
