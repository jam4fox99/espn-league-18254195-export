import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { RecordBook } from "@/components/record-book";

type RecordBookPageProps = {
  readonly params: Promise<{
    readonly leagueId: string;
  }>;
};

export default async function RecordBookPage({ params }: RecordBookPageProps) {
  const { leagueId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <RecordBook leagueId={leagueId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
