"use client";

import { useEffect, useState } from "react";
import { AppFrame } from "@/components/app-frame";
import { MetricStrip, ProductHeader } from "@/components/product-chrome";
import { OvrRing } from "@/components/rating-visuals";
import { StatusPill } from "@/components/status-pill";
import type { PublicShareData } from "@/lib/product-api";
import { readPublicShare } from "@/lib/product-api";
import { publicShareTitle, scoreLine } from "@/lib/product-model";

type ShareState =
  | { readonly kind: "loading" }
  | { readonly kind: "loaded"; readonly share: PublicShareData }
  | { readonly kind: "error"; readonly message: string };

export function PublicShareReport({ shareSlug }: { readonly shareSlug: string }) {
  const [state, setState] = useState<ShareState>({ kind: "loading" });

  useEffect(() => {
    let active = true;

    async function loadShare() {
      try {
        const share = await readPublicShare(shareSlug);
        if (active) {
          setState({ kind: "loaded", share });
        }
      } catch (error) {
        if (active) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Share report unavailable."
          });
        }
      }
    }

    void loadShare();
    return () => {
      active = false;
    };
  }, [shareSlug]);

  return (
    <AppFrame>
      {state.kind === "loading" ? (
        <section className="status-panel">
          <StatusPill tone="info">Loading</StatusPill>
          <h1>Loading public report</h1>
        </section>
      ) : null}
      {state.kind === "error" ? (
        <section className="status-panel">
          <StatusPill tone="error">Unavailable</StatusPill>
          <h1>Public report unavailable</h1>
          <p>{state.message}</p>
        </section>
      ) : null}
      {state.kind === "loaded" ? <ShareCard share={state.share} /> : null}
    </AppFrame>
  );
}

function ShareCard({ share }: { readonly share: PublicShareData }) {
  return (
    <section className="public-share" aria-labelledby="share-title">
      <ProductHeader eyebrow="Public report card" title={publicShareTitle(share)}>
        <StatusPill tone="success">Privacy-safe</StatusPill>
      </ProductHeader>
      <div className="share-hero">
        <OvrRing ovr={share.compositeScore} size={120} stroke={9} />
        <div className="share-hero__meta">
          <p className="section-kicker">Composite OVR</p>
          <p className="share-hero__sub">
            {share.confidence
              ? `Confidence: ${share.confidence}`
              : "Value captured, not a projection"}
          </p>
        </div>
      </div>
      <MetricStrip
        metrics={[
          {
            label: share.productLabel ?? share.ratingLabel ?? "Retrospective GM Rating",
            value: scoreLine(share.compositeScore),
            detail: share.confidence ?? "Confidence pending API field"
          },
          {
            label: "Formula version",
            value: share.formulaVersion ?? "current",
            detail: "Retrospective value captured only."
          },
          {
            label: "Best value-captured move",
            value: share.bestMove ?? "Pending API field",
            detail: "No private artifacts or import logs."
          }
        ]}
      />
      <article className="product-panel">
        <h2 id="share-title">Privacy boundary</h2>
        <p>{share.privacy}</p>
        <ul className="plain-list">
          {(share.caveats ?? ["2026 excluded from career ratings"]).map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      </article>
    </section>
  );
}
