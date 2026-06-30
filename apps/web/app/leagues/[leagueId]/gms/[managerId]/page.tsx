import { ManagerReport } from "@/components/analytics-page";
import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";

type ManagerPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
    readonly managerId: string;
  }>;
};

export default async function ManagerPage({ params }: ManagerPageProps) {
  const { leagueId, managerId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <ManagerReport leagueId={leagueId} managerId={managerId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
