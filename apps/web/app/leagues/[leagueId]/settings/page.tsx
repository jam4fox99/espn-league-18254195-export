import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { ShareSettings } from "@/components/share-settings";

type LeagueSettingsPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function LeagueSettingsPage({ params }: LeagueSettingsPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <ShareSettings leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
