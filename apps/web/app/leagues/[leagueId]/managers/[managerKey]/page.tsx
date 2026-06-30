import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { FranchiseHub } from "@/components/franchise-hub";

type FranchisePageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
    readonly managerKey: string;
  }>;
};

export default async function FranchisePage({ params }: FranchisePageProps) {
  const { leagueId, managerKey } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <FranchiseHub leagueId={leagueId} managerKey={decodeURIComponent(managerKey)} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
