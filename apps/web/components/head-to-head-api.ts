import ky, { HTTPError } from "ky";
import { z } from "zod";
import { readPublicEnv } from "@/lib/env";
import type { AlphaSession } from "@/lib/session";
import { createAlphaBearer } from "@/lib/session";

const managerRowSchema = z.object({
  managerKey: z.string().min(1),
  displayName: z.string().optional()
});

const managersResponseSchema = z.object({
  rows: z.array(managerRowSchema)
});

const matchupValueSchema = z.union([z.string(), z.number(), z.boolean(), z.null()]);
const matchupSchema = z.record(z.string(), matchupValueSchema);

const pairSchema = z.object({
  pairId: z.string().min(1),
  managerAKey: z.string().min(1),
  managerBKey: z.string().min(1),
  managerADisplayName: z.string().optional(),
  managerBDisplayName: z.string().optional(),
  managerAWins: z.number().int().nonnegative().optional(),
  managerBWins: z.number().int().nonnegative().optional(),
  ties: z.number().int().nonnegative().optional(),
  averageScore: z.number().optional(),
  biggestWin: z.string().optional(),
  streak: z.string().optional(),
  matchups: z.array(matchupSchema),
  caveats: z.array(z.string())
});

const headToHeadResponseSchema = z.object({
  pairs: z.array(pairSchema)
});

export type ManagerOption = z.infer<typeof managerRowSchema>;
export type HeadToHeadPair = z.infer<typeof pairSchema>;
export type MatchupValue = z.infer<typeof matchupValueSchema>;

export async function readManagers(
  session: AlphaSession,
  leagueId: string
): Promise<readonly ManagerOption[]> {
  const payload = await protectedJson(
    session,
    `v1/leagues/${leagueId}/gms?scope=all_time&version=current`
  );
  const parsed = managersResponseSchema.parse(payload);
  return parsed.rows;
}

export async function readHeadToHead(
  session: AlphaSession,
  leagueId: string,
  season: string,
  managerA: string,
  managerB: string
): Promise<z.infer<typeof headToHeadResponseSchema>> {
  const search = new URLSearchParams({ season, managerA, managerB });
  const payload = await protectedJson(
    session,
    `v1/leagues/${leagueId}/head-to-head?${search.toString()}`
  );
  return headToHeadResponseSchema.parse(payload);
}

async function protectedJson(session: AlphaSession, path: string): Promise<unknown> {
  const client = ky.create({
    baseUrl: readPublicEnv().NEXT_PUBLIC_API_BASE_URL,
    retry: 0,
    timeout: 10000
  });

  try {
    return await client(path, {
      headers: { Authorization: `Bearer ${createAlphaBearer(session)}` }
    }).json();
  } catch (error) {
    if (error instanceof HTTPError) {
      throw new Error(`API request failed for ${path}: ${error.response.status}`);
    }
    throw error;
  }
}
