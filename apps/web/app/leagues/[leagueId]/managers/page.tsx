import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { ManagersDirectory } from "@/components/managers-directory";

type ManagersPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function ManagersPage({ params }: ManagersPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <ManagersDirectory leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
