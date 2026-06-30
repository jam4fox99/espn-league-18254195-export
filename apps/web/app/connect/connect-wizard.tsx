"use client";

import { Send, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { FormEvent } from "react";
import { useState } from "react";
import { Select } from "@/components/controls";
import type { ConnectResult } from "@/lib/api-contract";
import { submitConnectForm } from "@/lib/api-contract";
import { ensureAlphaTestSession } from "@/lib/session";

const START_SEASONS = [2020, 2021, 2022].map((year) => ({
  value: String(year),
  label: String(year)
}));
const END_SEASONS = [2024, 2025].map((year) => ({ value: String(year), label: String(year) }));

type ConnectState =
  | { readonly kind: "idle" }
  | { readonly kind: "submitting" }
  | { readonly kind: "success"; readonly runId: string; readonly leagueUuid: string }
  | { readonly kind: "error"; readonly message: string };

export function ConnectWizard() {
  const [leagueId, setLeagueId] = useState("");
  const [swid, setSwid] = useState("");
  const [espnS2, setEspnS2] = useState("");
  const [startYear, setStartYear] = useState(2020);
  const [endYear, setEndYear] = useState(2025);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [connectState, setConnectState] = useState<ConnectState>({ kind: "idle" });

  async function submitConnect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setConnectState({ kind: "submitting" });

    const session = ensureAlphaTestSession(window.localStorage);

    try {
      const result = await submitConnectForm(
        {
          leagueId,
          swid,
          espnS2,
          startYear,
          endYear,
          consentAccepted
        },
        session
      );
      setConnectState(mapConnectResult(result));
    } catch {
      setConnectState({
        kind: "error",
        message: "Import could not be queued. Check API status and try again."
      });
    } finally {
      setSwid("");
      setEspnS2("");
    }
  }

  return (
    <form className="field-stack" onSubmit={submitConnect}>
      {connectState.kind === "error" ? (
        <p className="form-error" role="alert">
          {connectState.message}
        </p>
      ) : null}
      {connectState.kind === "success" ? (
        <p className="form-success" role="status">
          Import queued.{" "}
          <Link className="mono" href={`/import-runs/${connectState.runId}`}>
            View run {connectState.runId}
          </Link>
          {" · "}
          <Link href={`/leagues/${connectState.leagueUuid}`}>Open dashboard</Link>
        </p>
      ) : null}
      <label className="field-label">
        ESPN league ID
        <input
          inputMode="numeric"
          name="leagueId"
          onChange={(event) => setLeagueId(event.target.value)}
          required={true}
          value={leagueId}
        />
      </label>
      <label className="field-label">
        SWID
        <input
          autoComplete="off"
          name="swid"
          onChange={(event) => setSwid(event.target.value)}
          placeholder="{TEST-SWID}"
          required={true}
          value={swid}
        />
      </label>
      <label className="field-label">
        espn_s2
        <input
          autoComplete="off"
          name="espn_s2"
          onChange={(event) => setEspnS2(event.target.value)}
          placeholder="test-token"
          required={true}
          type="password"
          value={espnS2}
        />
      </label>
      <div className="season-row">
        <div className="field-label">
          Start season
          <Select
            ariaLabel="Start season"
            onChange={(value) => setStartYear(Number(value))}
            options={START_SEASONS}
            value={String(startYear)}
          />
        </div>
        <div className="field-label">
          End season
          <Select
            ariaLabel="End season"
            onChange={(value) => setEndYear(Number(value))}
            options={END_SEASONS}
            value={String(endYear)}
          />
        </div>
      </div>
      <label className="check-row">
        <input
          checked={consentAccepted}
          name="consent"
          onChange={(event) => setConsentAccepted(event.target.checked)}
          required={true}
          type="checkbox"
        />
        <span>
          I confirm this is an unofficial user-authorized ESPN cookie import, cookies are encrypted
          server-side, cookies can expire, and I am authorized to import this league.
        </span>
      </label>
      <button
        className="primary-action"
        disabled={connectState.kind === "submitting" || !consentAccepted}
        type="submit"
      >
        {connectState.kind === "submitting" ? (
          <Send aria-hidden="true" size={18} />
        ) : (
          <ShieldCheck aria-hidden="true" size={18} />
        )}
        Start import
      </button>
    </form>
  );
}

function mapConnectResult(result: ConnectResult): ConnectState {
  switch (result.kind) {
    case "queued":
      return { kind: "success", runId: result.run.runId, leagueUuid: result.run.leagueUuid };
    case "credential-error":
      return { kind: "error", message: result.message };
    default:
      return assertNever(result);
  }
}

function assertNever(value: never): never {
  throw new Error(`Unexpected connect result: ${JSON.stringify(value)}`);
}
