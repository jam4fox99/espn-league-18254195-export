import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { WaiversPage as WaiversClientPage } from "@/components/waivers-page";

type WaiversPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function WaiversPage({ params }: WaiversPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <WaiversClientPage leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
