import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { DataHealthPage } from "@/components/data-health-page";

type DataHealthRouteProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function DataHealthRoute({ params }: DataHealthRouteProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <DataHealthPage leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
