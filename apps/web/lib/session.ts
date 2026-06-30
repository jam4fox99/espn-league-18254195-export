import { z } from "zod";

const sessionKey = "mygm.alpha.session";

export const alphaSessionSchema = z.object({
  userId: z.string().min(1),
  email: z.string().email(),
  alphaAccepted: z.boolean(),
  inviteCode: z.string().min(1).optional(),
  internalAdmin: z.boolean()
});

export type AlphaSession = z.infer<typeof alphaSessionSchema>;

export type SessionResult =
  | { readonly kind: "signed-out" }
  | { readonly kind: "signed-in"; readonly session: AlphaSession };

const localAlphaSession: AlphaSession = {
  userId: "local-alpha-user",
  email: "alpha@example.com",
  alphaAccepted: true,
  inviteCode: "alpha-test",
  internalAdmin: false
};

export function readSession(storage: Storage): SessionResult {
  const value = storage.getItem(sessionKey);
  if (value === null) {
    return { kind: "signed-out" };
  }

  const parsedJson = parseStoredSession(value);
  const parsedSession = alphaSessionSchema.safeParse(parsedJson);
  if (!parsedSession.success) {
    storage.removeItem(sessionKey);
    return { kind: "signed-out" };
  }

  return { kind: "signed-in", session: parsedSession.data };
}

function parseStoredSession(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch (error) {
    if (error instanceof SyntaxError) {
      return null;
    }
    throw error;
  }
}

export function writeSession(storage: Storage, session: AlphaSession): void {
  storage.setItem(sessionKey, JSON.stringify(session));
}

export function ensureAlphaTestSession(storage: Storage): AlphaSession {
  const sessionResult = readSession(storage);
  if (sessionResult.kind === "signed-in" && sessionResult.session.alphaAccepted) {
    return sessionResult.session;
  }

  writeSession(storage, localAlphaSession);
  return localAlphaSession;
}

export function createAlphaBearer(session: AlphaSession): string {
  const role = session.internalAdmin ? "admin" : "user";
  return `alpha:${session.userId}:${session.email}:${role}`;
}

export function clearSession(storage: Storage): void {
  storage.removeItem(sessionKey);
}
