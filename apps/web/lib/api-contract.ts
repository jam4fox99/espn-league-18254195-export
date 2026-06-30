import { z } from "zod";
import {
  ApiClientError,
  acceptAlphaInvite,
  createLeague,
  enqueueImportRun,
  getImportRunStatus,
  storeCredentials,
  validateCredentials
} from "@/lib/api-client";
import type { AlphaSession } from "@/lib/session";

export const importRunStateSchema = z.enum([
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancel_requested",
  "cancelled",
  "dead"
]);

export const stepStateSchema = z.enum([
  "pending",
  "running",
  "succeeded",
  "retry_scheduled",
  "failed_retryable",
  "failed_terminal",
  "skipped"
]);

export const importRunSchema = z.object({
  runId: z.string().uuid(),
  leagueUuid: z.string().uuid(),
  state: importRunStateSchema,
  currentStep: z.string(),
  warningCount: z.number().int().nonnegative(),
  sourceCount: z.number().int().nonnegative(),
  credentialVersion: z.number().int().positive(),
  steps: z.array(
    z.object({
      name: z.string(),
      state: stepStateSchema,
      detail: z.string()
    })
  )
});

export type ImportRun = z.infer<typeof importRunSchema>;

export type ConnectForm = {
  readonly leagueId: string;
  readonly swid: string;
  readonly espnS2: string;
  readonly startYear: number;
  readonly endYear: number;
  readonly consentAccepted: boolean;
};

export type ConnectResult =
  | { readonly kind: "queued"; readonly run: ImportRun }
  | { readonly kind: "credential-error"; readonly message: string };

export async function submitConnectForm(
  form: ConnectForm,
  session: AlphaSession
): Promise<ConnectResult> {
  await Promise.resolve();

  if (!form.consentAccepted) {
    return {
      kind: "credential-error",
      message: "ESPN consent is required before credentials can be stored."
    };
  }

  try {
    await acceptAlphaInvite(session, session.inviteCode ?? "alpha-test");
    const league = await createLeague(session, form.leagueId);
    await validateCredentials(session, league.leagueUuid, form);
    const credentials = await storeCredentials(session, league.leagueUuid, form);
    const importRun = await enqueueImportRun(session, league.leagueUuid, form);
    return {
      kind: "queued",
      run: createQueuedRun({
        runId: importRun.runId,
        leagueUuid: league.leagueUuid,
        credentialVersion: credentials.credentialVersion,
        form
      })
    };
  } catch (error) {
    if (error instanceof ApiClientError) {
      if (error.status === 400 || error.status === 401 || error.status === 403) {
        return {
          kind: "credential-error",
          message: "Credential validation failed. Check ESPN cookies and try again."
        };
      }
      throw error;
    }

    if (error instanceof TypeError) {
      return {
        kind: "credential-error",
        message:
          "API connection unavailable. Run the local API at 127.0.0.1:8000 or configure a deployed NEXT_PUBLIC_API_BASE_URL."
      };
    }

    throw error;
  }
}

function createQueuedRun({
  runId,
  leagueUuid,
  credentialVersion,
  form
}: {
  readonly runId: string;
  readonly leagueUuid: string;
  readonly credentialVersion: number;
  readonly form: ConnectForm;
}): ImportRun {
  const run = importRunSchema.parse({
    runId,
    leagueUuid,
    state: "queued",
    currentStep: "fetch_core",
    warningCount: 0,
    sourceCount: 0,
    credentialVersion,
    steps: [
      {
        name: "fetch_core",
        state: "pending",
        detail: `League ${form.leagueId} seasons ${form.startYear}-${form.endYear}`
      },
      {
        name: "store_raw_manifest",
        state: "pending",
        detail: "Raw artifacts remain private."
      },
      {
        name: "publish_snapshot",
        state: "pending",
        detail: "Current version moves only after validation."
      }
    ]
  });

  return run;
}

export async function readImportRun(runId: string, session: AlphaSession): Promise<ImportRun> {
  const status = await getImportRunStatus(session, runId);

  return importRunSchema.parse({
    runId: status.runId,
    leagueUuid: status.leagueUuid,
    state: status.status,
    currentStep: status.step,
    warningCount: status.warnings.length,
    sourceCount: 0,
    credentialVersion: status.credentialVersion,
    steps: [
      {
        name: status.step,
        state: status.status === "succeeded" ? "succeeded" : "running",
        detail:
          status.warnings.length > 0
            ? `${status.warnings.length} warning(s) recorded.`
            : "Worker status returned without exposing artifacts."
      }
    ]
  });
}
