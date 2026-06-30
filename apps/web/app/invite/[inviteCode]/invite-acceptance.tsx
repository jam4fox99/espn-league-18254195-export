"use client";

import { CheckCircle2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { acceptAlphaInvite } from "@/lib/api-client";
import { readSession, writeSession } from "@/lib/session";

type InviteAcceptanceProps = {
  readonly inviteCode: string;
};

export function InviteAcceptance({ inviteCode }: InviteAcceptanceProps) {
  const router = useRouter();

  async function acceptInvite() {
    const sessionResult = readSession(window.localStorage);
    const currentSession =
      sessionResult.kind === "signed-in"
        ? sessionResult.session
        : {
            userId: "local-alpha-user",
            email: "alpha@example.com",
            alphaAccepted: false,
            internalAdmin: false
          };

    try {
      await acceptAlphaInvite(currentSession, inviteCode);
    } catch (error) {
      if (!(error instanceof TypeError)) {
        throw error;
      }
    }

    writeSession(window.localStorage, {
      userId: currentSession.userId,
      email: currentSession.email,
      alphaAccepted: true,
      inviteCode,
      internalAdmin: currentSession.internalAdmin
    });
    router.push("/connect");
  }

  return (
    <div className="field-stack">
      <p className="form-success">Invite recognized. Accept to unlock the ESPN connect flow.</p>
      <button className="primary-action" onClick={acceptInvite} type="button">
        <CheckCircle2 aria-hidden="true" size={18} />
        Accept invite
      </button>
    </div>
  );
}
