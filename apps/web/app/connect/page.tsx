import { AppFrame } from "@/components/app-frame";
import { ClientOnly } from "@/components/client-only";
import { ConnectWizard } from "./connect-wizard";

export default function ConnectPage() {
  return (
    <AppFrame>
      <ClientOnly>
        <section className="connect-grid" aria-labelledby="connect-title">
          <div className="form-panel">
            <h1 id="connect-title">Connect ESPN league</h1>
            <p>
              Enter the ESPN league cookies for an authorized test import. The app creates the
              private-alpha session locally; ESPN secrets still go only to the API and are cleared
              from the form after submit.
            </p>
            <ConnectWizard />
          </div>
          <aside className="evidence-panel" aria-label="Credential guidance">
            <h2>Credential handling</h2>
            <dl>
              <div>
                <dt>Required inputs</dt>
                <dd>League ID, SWID, espn_s2, and selected seasons.</dd>
              </div>
              <div>
                <dt>Consent</dt>
                <dd>Confirm you are authorized to import this ESPN league.</dd>
              </div>
              <div>
                <dt>After submit</dt>
                <dd>SWID and espn_s2 are blanked from the browser form.</dd>
              </div>
            </dl>
          </aside>
        </section>
      </ClientOnly>
    </AppFrame>
  );
}
