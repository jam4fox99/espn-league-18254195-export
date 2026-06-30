import { AdminImportRuns } from "@/components/admin-import-runs";
import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";

export default function AdminImportRunsPage() {
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <AdminImportRuns />
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
