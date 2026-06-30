import { ImageResponse } from "next/og";
import { createElement as h } from "react";
import { readPublicShare } from "@/lib/product-api";

type OgRouteProps = {
  readonly params: Promise<{
    readonly shareSlug: string;
  }>;
};

const WIDTH = 1200;
const HEIGHT = 630;

/**
 * Privacy-safe, 2K/MyGM-Menu-styled Open Graph card. Renders only public
 * fields (manager/team title, composite GM rating, confidence). Falls back to a
 * branded card if the share payload is unavailable. (§5 / decision 3)
 */
export async function GET(_request: Request, { params }: OgRouteProps) {
  const { shareSlug } = await params;

  let title = "Retrospective GM Rating";
  let score = "—";
  let confidence = "";
  try {
    const share = await readPublicShare(shareSlug);
    title = share.teamName ?? share.managerName ?? share.title ?? share.productLabel ?? title;
    score = typeof share.compositeScore === "number" ? share.compositeScore.toFixed(1) : score;
    confidence = share.confidence ?? "";
  } catch {
    // Branded fallback card below.
  }

  return new ImageResponse(
    h(
      "div",
      {
        style: {
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          color: "#EAF0FB",
          background: "linear-gradient(135deg, #0A0E1A 0%, #1B2A52 50%, #0A0E1A 100%)"
        }
      },
      h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: 18 } },
        h("div", {
          style: { width: 14, height: 44, background: "#FFE600", transform: "skewX(-12deg)" }
        }),
        h("div", { style: { fontSize: 40, fontWeight: 800, letterSpacing: 2 } }, "MyGM"),
        h(
          "div",
          { style: { fontSize: 22, color: "#9DAAC2", letterSpacing: 4, marginLeft: 8 } },
          "RETROSPECTIVE GM RATING"
        )
      ),
      h(
        "div",
        { style: { display: "flex", flexDirection: "column", gap: 8 } },
        h(
          "div",
          { style: { fontSize: 76, fontWeight: 800, lineHeight: 1.02, display: "flex" } },
          title
        ),
        h(
          "div",
          { style: { display: "flex", alignItems: "flex-end", gap: 20, marginTop: 12 } },
          h(
            "div",
            { style: { fontSize: 150, fontWeight: 900, color: "#FFE600", lineHeight: 1 } },
            score
          ),
          h("div", { style: { fontSize: 34, color: "#9DAAC2", paddingBottom: 22 } }, "OVR")
        )
      ),
      h(
        "div",
        { style: { fontSize: 24, color: "#9DAAC2", display: "flex" } },
        confidence
          ? `Confidence: ${confidence} · value captured, not a projection`
          : "Value captured, not a projection · luck excluded"
      )
    ),
    { width: WIDTH, height: HEIGHT }
  );
}
