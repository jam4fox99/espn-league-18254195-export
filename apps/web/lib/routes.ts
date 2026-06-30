export const routePaths = {
  home: "/",
  connect: "/connect",
  invite: (inviteCode: string) => `/invite/${inviteCode}`,
  importRun: (runId: string) => `/import-runs/${runId}`,
  league: (leagueId: string) => `/leagues/${leagueId}`,
  leagueSettings: (leagueId: string) => `/leagues/${leagueId}/settings`
} as const;
