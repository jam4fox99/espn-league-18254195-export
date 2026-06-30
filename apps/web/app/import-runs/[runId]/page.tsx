import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { ImportRunStatus } from "./status";

type ImportRunPageProps = {
  readonly params: Promise<{
    readonly runId: string;
  }>;
};

export default async function ImportRunPage({ params }: ImportRunPageProps) {
  const { runId } = await params;
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <ImportRunStatus runId={runId} />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
