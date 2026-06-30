import { GmRatingsPage } from "@/components/analytics-page";
import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";

type GmsPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function GmsPage({ params }: GmsPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <GmRatingsPage leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
