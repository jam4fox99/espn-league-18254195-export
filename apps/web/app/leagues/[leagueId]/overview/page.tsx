import { redirect } from "next/navigation";

type OverviewPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

// /overview is an alias of Home (next-build goal, Priority 4): the league
// dashboard was rebuilt in place at the root route. Keep the legacy URL working.
export default async function OverviewPage({ params }: OverviewPageProps) {
  const { leagueId } = await params;
  redirect(`/leagues/${leagueId}`);
}
