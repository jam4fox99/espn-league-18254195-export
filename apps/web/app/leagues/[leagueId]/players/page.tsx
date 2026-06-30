import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { PlayersPage } from "@/components/players-page";

type PlayersRouteProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function PlayersRoute({ params }: PlayersRouteProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <PlayersPage leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
