import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { LeagueHistory } from "@/components/league-history";

type HistoryPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function HistoryPage({ params }: HistoryPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <LeagueHistory leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
