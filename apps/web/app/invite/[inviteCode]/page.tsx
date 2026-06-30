import { AppFrame } from "@/components/app-frame";
import { InviteAcceptance } from "./invite-acceptance";

type InvitePageProps = {
  readonly params: Promise<{
    readonly inviteCode: string;
  }>;
};

export default async function InvitePage({ params }: InvitePageProps) {
  const { inviteCode } = await params;
  return (
    <AppFrame>
      <section className="auth-grid" aria-labelledby="invite-title">
        <div className="form-panel">
          <h1 id="invite-title">Accept private alpha invite</h1>
          <p>
            This gate links your signed-in account to the private alpha before ESPN credentials or
            league data can be handled.
          </p>
          <InviteAcceptance inviteCode={inviteCode} />
        </div>
        <aside className="evidence-panel" aria-label="Invite boundaries">
          <h2>Access boundary</h2>
          <dl>
            <div>
              <dt>Code</dt>
              <dd className="mono">{inviteCode}</dd>
            </div>
            <div>
              <dt>Next action</dt>
              <dd>Connect an authorized ESPN league after acceptance.</dd>
            </div>
          </dl>
        </aside>
      </section>
    </AppFrame>
  );
}
