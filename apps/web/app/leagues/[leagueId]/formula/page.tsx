import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { FormulaPage } from "@/components/formula-page";

type FormulaRouteProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function FormulaRoute({ params }: FormulaRouteProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <FormulaPage leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
