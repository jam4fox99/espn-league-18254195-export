"use client";

import { useCallback, useState } from "react";
import { LeagueNav, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import type { ShareLinkData } from "@/lib/product-api";
import { createShareLink, readShareLinks, revokeShareLink } from "@/lib/product-api";
import { fixtureIds } from "@/lib/product-copy";
import type { AlphaSession } from "@/lib/session";

export function ShareSettings({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback(
    (session: AlphaSession) => readShareLinks(session, leagueId),
    [leagueId]
  );

  return (
    <ProductLoader load={load}>
      {(links, session) => (
        <ShareSettingsPanel initialLinks={links} leagueId={leagueId} session={session} />
      )}
    </ProductLoader>
  );
}

function ShareSettingsPanel({
  initialLinks,
  leagueId,
  session
}: {
  readonly initialLinks: readonly ShareLinkData[];
  readonly leagueId: string;
  readonly session: AlphaSession;
}) {
  const [links, setLinks] = useState<readonly ShareLinkData[]>(initialLinks);
  const [message, setMessage] = useState<string | null>(null);

  async function createShare() {
    const link = await createShareLink(
      session,
      leagueId,
      fixtureIds.managerId,
      fixtureIds.versionId
    );
    setLinks([link, ...links.filter((existing) => existing.shareLinkId !== link.shareLinkId)]);
    setMessage("Privacy-safe share link created.");
  }

  async function revokeShare(shareLinkId: string) {
    const revoked = await revokeShareLink(session, shareLinkId);
    setLinks(links.map((link) => (link.shareLinkId === revoked.shareLinkId ? revoked : link)));
    setMessage("Share link revoked.");
  }

  return (
    <section className="product-stack">
      <LeagueNav leagueId={leagueId} />
      <ProductHeader eyebrow="League settings" leagueId={leagueId} title="Share management">
        <button className="primary-action" onClick={createShare} type="button">
          Create share
        </button>
      </ProductHeader>
      {message ? (
        <p className="form-success" role="status">
          {message}
        </p>
      ) : null}
      <table className="data-table">
        <caption>Privacy-safe public report links</caption>
        <thead>
          <tr>
            <th scope="col">Slug</th>
            <th scope="col">Status</th>
            <th scope="col">Public route</th>
            <th scope="col">Action</th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => (
            <tr key={link.shareLinkId}>
              <th scope="row">{link.shareSlug}</th>
              <td>
                <StatusPill tone={link.revoked ? "warning" : "success"}>
                  {link.revoked ? "Revoked" : "Active"}
                </StatusPill>
              </td>
              <td>
                <a className="mono" href={`/s/${link.shareSlug}`}>
                  /s/{link.shareSlug}
                </a>
              </td>
              <td>
                <button
                  className="secondary-action"
                  disabled={link.revoked}
                  onClick={() => void revokeShare(link.shareLinkId)}
                  type="button"
                >
                  Revoke
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="notice-line">
        Public shares omit internal IDs, private emails, ESPN cookies, import logs, and private
        artifact paths.
      </p>
    </section>
  );
}
