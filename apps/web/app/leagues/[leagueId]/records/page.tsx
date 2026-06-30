import { redirect } from "next/navigation";

type RecordsPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

// Legacy /records → the Record Book (next-build goal, Priority 4).
export default async function RecordsPage({ params }: RecordsPageProps) {
  const { leagueId } = await params;
  redirect(`/leagues/${leagueId}/record-book`);
}
