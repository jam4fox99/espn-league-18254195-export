import { AppFrame } from "@/components/app-frame";
import { AuthGate } from "@/components/auth-gate";
import { ClientOnly } from "@/components/client-only";
import { StatusPill } from "@/components/status-pill";

type ProtectedPlaceholderProps = {
  readonly eyebrow: string;
  readonly heading: string;
  readonly leagueId: string;
};

export function ProtectedPlaceholder({ eyebrow, heading, leagueId }: ProtectedPlaceholderProps) {
  return (
    <AppFrame>
      <ClientOnly>
        <AuthGate>
          <section className="status-panel" aria-labelledby="protected-title">
            <StatusPill tone="info">{eyebrow}</StatusPill>
            <h1 id="protected-title">{heading}</h1>
            <p>
              League context <span className="mono">{leagueId}</span> is protected by invite access.
              Analytics surfaces will bind to D/C contracts after Task 7 accepts API and fixture
              output handoffs.
            </p>
          </section>
        </AuthGate>
      </ClientOnly>
    </AppFrame>
  );
}
