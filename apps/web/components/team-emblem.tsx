"use client";

import { useState } from "react";
import { monogram } from "../lib/images";

interface TeamEmblemProps {
  /** Resolved logo URL (local /logos path or remote ESPN url), or null. */
  readonly logo?: string | null | undefined;
  /** Team or manager name — used for the monogram fallback + alt text. */
  readonly name: string;
  /** Pixel size of the square emblem. */
  readonly size?: number | undefined;
  /** Highlight as the owner ("you") with the yellow plinth. */
  readonly you?: boolean | undefined;
  readonly className?: string | undefined;
}

/**
 * Team logo on a dark angular plinth. On load error (dead/rotted logo) or when
 * no logo is supplied, falls back to monogram initials — never a broken image.
 * Logos can be SVG (ESPN VECTOR), raster, or local baked files, so we use a
 * plain <img> for uniform handling + reliable onError. (§7d / §11)
 */
export function TeamEmblem({ logo, name, size = 44, you = false, className }: TeamEmblemProps) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(logo) && !failed;
  const classes = ["team-emblem"];
  if (you) {
    classes.push("team-emblem--you");
  }
  if (className) {
    classes.push(className);
  }

  return (
    <span
      className={classes.join(" ")}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.36) }}
      role="img"
      aria-label={name}
      title={name}
    >
      {showImage ? (
        // biome-ignore lint/performance/noImgElement: SVG logos + onError fallback need a plain <img>.
        <img
          src={logo ?? undefined}
          alt={name}
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="team-emblem__monogram" aria-hidden="true">
          {monogram(name)}
        </span>
      )}
    </span>
  );
}
