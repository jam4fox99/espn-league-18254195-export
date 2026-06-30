import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { TradesPage as TradesClientPage } from "@/components/trades-page";

type TradesPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function TradesPage({ params }: TradesPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <TradesClientPage leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
