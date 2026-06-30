import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { RivalriesMatrix } from "@/components/rivalries-matrix";

type RivalriesPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function RivalriesPage({ params }: RivalriesPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <RivalriesMatrix leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
