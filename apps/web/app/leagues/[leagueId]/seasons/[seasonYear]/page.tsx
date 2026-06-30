import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { SeasonHub } from "@/components/season-hub";

type SeasonPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
    readonly seasonYear: string;
  }>;
};

export default async function SeasonPage({ params }: SeasonPageProps) {
  const { leagueId, seasonYear } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <SeasonHub leagueId={leagueId} season={seasonYear} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
