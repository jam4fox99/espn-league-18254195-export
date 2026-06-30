"use client";

import { type CSSProperties, useEffect, useId, useRef, useState } from "react";
import { ovrTier } from "../lib/images";

interface OvrRingProps {
  /** 0–100 overall, or null when withheld/ineligible. */
  readonly ovr: number | null | undefined;
  readonly size?: number;
  readonly stroke?: number;
  /** Withheld/ineligible/unresolved → dimmed ring + UNRATED, never a number. */
  readonly withheld?: boolean;
  /** Reason shown on hover for an UNRATED plate. */
  readonly unratedReason?: string;
  readonly label?: string;
}

/**
 * Circular OVR ring: arc swept to value, colored by tier, number centered.
 * Withheld/ineligible renders a dimmed ring with an explicit `UNRATED` plate
 * and no fabricated numeral (decision 4 / §10). Reduced-motion is handled
 * globally (transition-duration collapses), so the final offset is the target.
 */
export function OvrRing({
  ovr,
  size = 56,
  stroke = 5,
  withheld = false,
  unratedReason,
  label = "OVR"
}: OvrRingProps) {
  const isUnrated = withheld || ovr == null || Number.isNaN(ovr);
  const value = isUnrated ? 0 : Math.max(0, Math.min(100, ovr));
  const tier = ovrTier(value);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const target = circumference * (1 - value / 100);

  const [filled, setFilled] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setFilled(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  const offset = isUnrated ? circumference : filled ? target : circumference;
  const color = isUnrated ? "var(--tier-low)" : tier.color;

  return (
    <span
      className={`ovr-ring${isUnrated ? " ovr-ring--unrated" : ""}`}
      style={{ width: size, height: size }}
      title={isUnrated ? unratedReason : undefined}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,.08)"
          strokeWidth={stroke}
        />
        {!isUnrated ? (
          <circle
            className="ovr-ring__arc"
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        ) : null}
      </svg>
      <span className="ovr-ring__center">
        {isUnrated ? (
          <span className="ovr-ring__unrated">UNRATED</span>
        ) : (
          <>
            {size >= 90 ? <span className="ovr-ring__label">{label}</span> : null}
            <span className="ovr-ring__num" style={{ color }}>
              {Math.round(value)}
            </span>
          </>
        )}
      </span>
    </span>
  );
}

interface SegmentedMeterProps {
  /** 0–100 attribute value, or null/undefined when not applicable. */
  readonly value: number | null | undefined;
  readonly cells?: number;
  /** Stagger the fill (hero meters); off for dense row micro-meters. */
  readonly stagger?: boolean;
  readonly mini?: boolean;
}

/** Segmented (~10-cell) attribute meter, filled in tier color (§4). */
export function SegmentedMeter({
  value,
  cells = 10,
  stagger = false,
  mini = false
}: SegmentedMeterProps) {
  const id = useId();
  const v = value == null || Number.isNaN(value) ? 0 : Math.max(0, Math.min(100, value));
  const filledCount = Math.round((v / 100) * cells);
  const span = Math.max(cells - 1, 1);

  const [lit, setLit] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setLit(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <span className={`seg-meter${mini ? " seg-meter--mini" : ""}`} role="presentation">
      {Array.from({ length: cells }, (_, i) => {
        const on = i < filledCount;
        // Each chevron owns a fixed slot on a red→green ramp; the fill just reveals it,
        // so a low score lights only the red end and a high score climbs into green.
        const hue = Math.round((i / span) * 125);
        return (
          <span
            // biome-ignore lint/suspicious/noArrayIndexKey: segmented cells are fixed + positional.
            key={`${id}-${i}`}
            className={`seg-meter__cell${on && lit ? " is-on" : ""}`}
            style={
              {
                "--seg-hue": hue,
                transitionDelay: stagger ? `${i * 45}ms` : undefined
              } as CSSProperties
            }
          />
        );
      })}
    </span>
  );
}

/**
 * Fires `onEnter` once when the element scrolls into view — used to trigger
 * one-shot fills on showcase surfaces (§8). Returns a ref to attach.
 */
export function useInView<T extends HTMLElement>(onEnter: () => void) {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") {
      onEnter();
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            onEnter();
            observer.disconnect();
            return;
          }
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [onEnter]);
  return ref;
}
