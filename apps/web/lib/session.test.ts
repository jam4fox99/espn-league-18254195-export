import { beforeEach, describe, expect, it } from "vitest";
import { ensureAlphaTestSession, readSession, writeSession } from "./session";

describe("readSession", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("returns signed-out when local session data is malformed", () => {
    const storage = window.localStorage;
    storage.setItem("mygm.alpha.session", "{malformed");

    expect(readSession(storage)).toEqual({ kind: "signed-out" });
    expect(storage.getItem("mygm.alpha.session")).toBeNull();
  });

  it("round trips accepted alpha session metadata", () => {
    const storage = window.localStorage;
    writeSession(storage, {
      userId: "local-alpha-user",
      email: "alpha@example.com",
      alphaAccepted: true,
      inviteCode: "alpha-test",
      internalAdmin: false
    });

    expect(readSession(storage)).toEqual({
      kind: "signed-in",
      session: {
        userId: "local-alpha-user",
        email: "alpha@example.com",
        alphaAccepted: true,
        inviteCode: "alpha-test",
        internalAdmin: false
      }
    });
  });

  it("creates the local alpha session used by the no-login connect flow", () => {
    const storage = window.localStorage;

    expect(ensureAlphaTestSession(storage)).toEqual({
      userId: "local-alpha-user",
      email: "alpha@example.com",
      alphaAccepted: true,
      inviteCode: "alpha-test",
      internalAdmin: false
    });
    expect(readSession(storage)).toEqual({
      kind: "signed-in",
      session: {
        userId: "local-alpha-user",
        email: "alpha@example.com",
        alphaAccepted: true,
        inviteCode: "alpha-test",
        internalAdmin: false
      }
    });
  });
});
