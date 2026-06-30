import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PlayerChip, PlayerImage } from "./player-image";
import { OvrRing, SegmentedMeter } from "./rating-visuals";
import { TeamEmblem } from "./team-emblem";

// Render next/image as a plain <img> so we can assert raw src + onError deterministically.
vi.mock("next/image", () => ({
  default: ({
    priority: _priority,
    unoptimized: _unoptimized,
    ...rest
  }: Record<string, unknown>) => {
    // biome-ignore lint/performance/noImgElement: test shim for next/image.
    // biome-ignore lint/a11y/useAltText: alt is forwarded via rest props.
    return <img {...(rest as Record<string, unknown>)} />;
  }
}));

describe("TeamEmblem fallbacks", () => {
  it("renders the logo image when a url is supplied", () => {
    const { container } = render(<TeamEmblem logo="https://x/logo.png" name="Jake Milken" />);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toBe("https://x/logo.png");
  });

  it("falls back to a monogram when the logo fails to load (dead logo)", () => {
    const { container } = render(<TeamEmblem logo="https://x/dead.png" name="Jake Milken" />);
    fireEvent.error(container.querySelector("img") as HTMLImageElement);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("JM")).toBeInTheDocument();
  });

  it("shows a monogram immediately when no logo is provided", () => {
    render(<TeamEmblem logo={null} name="Doug" />);
    expect(screen.getByText("DO")).toBeInTheDocument();
  });
});

describe("PlayerImage fallbacks", () => {
  it("uses the headshot url for a real player", () => {
    const { container } = render(<PlayerImage playerId={3918298} name="Josh Allen" />);
    expect(container.querySelector("img")?.getAttribute("src")).toContain(
      "/i/headshots/nfl/players/full/3918298.png"
    );
  });

  it("uses the NFL team logo for a D/ST (negative id)", () => {
    const { container } = render(
      <PlayerImage playerId={-16034} name="Texans D/ST" teamAbbr="HOU" />
    );
    expect(container.querySelector("img")?.getAttribute("src")).toContain("/teamlogos/nfl/500/hou");
  });

  it("renders a silhouette when there is no id", () => {
    const { container } = render(<PlayerImage name="Unknown" />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("svg.player-image__silhouette")).not.toBeNull();
  });

  it("falls back to a silhouette when the headshot 404s", () => {
    const { container } = render(<PlayerImage playerId={999999} name="Ghost" />);
    fireEvent.error(container.querySelector("img") as HTMLImageElement);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("svg.player-image__silhouette")).not.toBeNull();
  });
});

describe("PlayerChip subtitle", () => {
  it("renders the TEAM + colored POS subtitle (Gibbs → DET RB)", () => {
    render(<PlayerChip playerId={1} name="Jahmyr Gibbs" teamAbbr="DET" position="RB" />);
    expect(screen.getByText("Jahmyr Gibbs")).toBeInTheDocument();
    expect(screen.getByText("DET")).toBeInTheDocument();
    const pos = screen.getByText("RB");
    expect(pos).toBeInTheDocument();
    // Position carries its fantasy-position accent (RB → --tier-elite).
    expect(pos).toHaveClass("player-chip-2k__pos");
    expect(pos).toHaveStyle({ color: "var(--tier-elite)" });
  });

  it("hides the subtitle in compact mode", () => {
    render(<PlayerChip playerId={1} name="Jahmyr Gibbs" teamAbbr="DET" position="RB" compact />);
    expect(screen.queryByText("DET")).toBeNull();
    expect(screen.queryByText("RB")).toBeNull();
  });
});

describe("OvrRing — UNRATED plate", () => {
  it("renders UNRATED with no numeral when withheld", () => {
    render(<OvrRing ovr={null} withheld unratedReason="Score withheld" />);
    expect(screen.getByText("UNRATED")).toBeInTheDocument();
  });

  it("renders the numeral when rated and reaches its final (filled) state", async () => {
    const { container } = render(<OvrRing ovr={72} size={56} stroke={5} />);
    expect(screen.getByText("72")).toBeInTheDocument();
    // The arc animates to its target offset (final state) after mount — the
    // reduced-motion guarantee is that the same final offset is reached.
    const circumference = 2 * Math.PI * ((56 - 5) / 2);
    await waitFor(() => {
      const arc = container.querySelector(".ovr-ring__arc") as SVGCircleElement;
      const offset = Number.parseFloat(arc.getAttribute("stroke-dashoffset") ?? "0");
      expect(offset).toBeLessThan(circumference);
    });
  });
});

describe("SegmentedMeter", () => {
  it("renders the requested number of cells", () => {
    const { container } = render(<SegmentedMeter value={60} cells={10} />);
    expect(container.querySelectorAll(".seg-meter__cell")).toHaveLength(10);
  });
});
