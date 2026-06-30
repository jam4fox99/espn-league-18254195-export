import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { LeagueHome } from "@/components/league-home";

type LeaguePageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function LeaguePage({ params }: LeaguePageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <LeagueHome leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
