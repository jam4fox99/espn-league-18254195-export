/**
 * Slow animated gradient wash — an ambient flourish reserved for the landing
 * and dashboard surfaces only (§8). Transform/opacity only; the animation is
 * disabled under prefers-reduced-motion in CSS.
 */
export function AmbientWash() {
  return <div className="ambient-wash" aria-hidden="true" />;
}
