import ky, { HTTPError } from "ky";
import { z } from "zod";
import { readPublicEnv } from "@/lib/env";
import type { AlphaSession } from "@/lib/session";
import { createAlphaBearer } from "@/lib/session";

const uuidSchema = z.string().uuid();

const leagueResponseSchema = z.object({
  league_id: uuidSchema.optional(),
  leagueId: uuidSchema.optional(),
  id: uuidSchema.optional()
});

const credentialResponseSchema = z.object({
  credentialVersion: z.number().int().positive().optional(),
  credential_version: z.number().int().positive().optional()
});

const importRunResponseSchema = z.object({
  run_id: uuidSchema.optional(),
  runId: uuidSchema.optional(),
  id: uuidSchema.optional(),
  league_id: uuidSchema.optional(),
  leagueId: uuidSchema.optional(),
  status: z.string().optional(),
  step: z.string().optional(),
  credentialVersion: z.number().int().positive().optional(),
  credential_version: z.number().int().positive().optional(),
  warnings: z.array(z.string()).optional()
});

export type ApiLeagueResult = {
  readonly leagueUuid: string;
};

export type ApiCredentialResult = {
  readonly credentialVersion: number;
};

export type ApiImportRunResult = {
  readonly runId: string;
};

export type ApiImportRunStatus = {
  readonly runId: string;
  readonly leagueUuid: string;
  readonly status: string;
  readonly step: string;
  readonly credentialVersion: number;
  readonly warnings: readonly string[];
};

export type ApiConnectRequest = {
  readonly leagueId: string;
  readonly swid: string;
  readonly espnS2: string;
  readonly startYear: number;
  readonly endYear: number;
};

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export async function createLeague(
  session: AlphaSession,
  leagueId: string
): Promise<ApiLeagueResult> {
  const parsed = leagueResponseSchema.parse(
    await apiJson(session, "v1/leagues", {
      method: "post",
      json: {
        espnLeagueId: leagueId,
        name: `ESPN league ${leagueId}`
      }
    })
  );

  const leagueUuid = uuidSchema.parse(parsed.league_id ?? parsed.leagueId ?? parsed.id);
  return {
    leagueUuid
  };
}

export async function storeCredentials(
  session: AlphaSession,
  leagueUuid: string,
  request: ApiConnectRequest
): Promise<ApiCredentialResult> {
  const parsed = credentialResponseSchema.parse(
    await apiJson(session, `v1/leagues/${leagueUuid}/credentials`, {
      method: "post",
      json: {
        leagueId: leagueUuid,
        SWID: request.swid,
        espn_s2: request.espnS2,
        consentVersion: "private-alpha-v1",
        startYear: request.startYear,
        endYear: request.endYear
      }
    })
  );

  return {
    credentialVersion: z
      .number()
      .int()
      .positive()
      .parse(parsed.credentialVersion ?? parsed.credential_version)
  };
}

export async function validateCredentials(
  session: AlphaSession,
  leagueUuid: string,
  _request: ApiConnectRequest
): Promise<void> {
  await apiJson(session, `v1/leagues/${leagueUuid}/credentials/validate`, {
    method: "post"
  });
}

export async function enqueueImportRun(
  session: AlphaSession,
  leagueUuid: string,
  request: ApiConnectRequest
): Promise<ApiImportRunResult> {
  const parsed = importRunResponseSchema.parse(
    await apiJson(session, `v1/leagues/${leagueUuid}/import-runs`, {
      method: "post",
      json: {
        startYear: request.startYear,
        endYear: request.endYear,
        includeActivity: true,
        forceRefresh: false
      }
    })
  );

  return {
    runId: uuidSchema.parse(parsed.run_id ?? parsed.runId ?? parsed.id)
  };
}

export async function getImportRunStatus(
  session: AlphaSession,
  runId: string
): Promise<ApiImportRunStatus> {
  const parsed = importRunResponseSchema.parse(await apiJson(session, `v1/import-runs/${runId}`));

  return {
    runId: uuidSchema.parse(parsed.run_id ?? parsed.runId ?? parsed.id),
    leagueUuid: uuidSchema.parse(parsed.league_id ?? parsed.leagueId),
    status: z.string().parse(parsed.status),
    step: z.string().parse(parsed.step),
    credentialVersion: z
      .number()
      .int()
      .positive()
      .parse(parsed.credentialVersion ?? parsed.credential_version),
    warnings: parsed.warnings ?? []
  };
}

export async function acceptAlphaInvite(session: AlphaSession, inviteCode: string): Promise<void> {
  await apiJson(session, "v1/alpha-invites/accept", {
    method: "post",
    json: {
      email: session.email,
      inviteCode
    }
  });
}

async function apiJson(
  session: AlphaSession,
  path: string,
  options: {
    readonly method: "post" | "patch" | "delete" | "get";
    readonly json?: unknown;
  } = { method: "get" }
): Promise<unknown> {
  const env = readPublicEnv();
  assertReachableApiBase(env.NEXT_PUBLIC_API_BASE_URL);
  const client = ky.create({
    baseUrl: env.NEXT_PUBLIC_API_BASE_URL,
    headers: {
      Authorization: `Bearer ${createAlphaBearer(session)}`
    },
    retry: 0,
    timeout: 10000
  });

  try {
    return await client(path, options).json();
  } catch (error) {
    if (error instanceof HTTPError) {
      throw new ApiClientError(`API request failed for ${path}`, error.response.status);
    }
    throw error;
  }
}

function assertReachableApiBase(baseUrl: string): void {
  if (typeof window === "undefined") {
    return;
  }

  const apiUrl = new URL(baseUrl);
  const pageHost = window.location.hostname;
  if (isLoopbackHost(apiUrl.hostname) && !isLoopbackHost(pageHost)) {
    throw new TypeError(
      "The configured API base URL points at a local-only backend from a hosted page."
    );
  }
}

function isLoopbackHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}
