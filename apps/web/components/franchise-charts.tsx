"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

const ACCENT = "#22d3ee";
const GRID = "rgba(148, 163, 184, 0.18)";
const AXIS_TEXT = "#94a3b8";

const tooltipStyle = {
  background: "#0b1620",
  border: "1px solid rgba(148, 163, 184, 0.25)",
  borderRadius: 10,
  color: "#e2e8f0",
  fontSize: 12
} as const;

export function RatingRadar({
  data
}: {
  readonly data: readonly { readonly component: string; readonly value: number }[];
}) {
  if (data.length === 0) {
    return <p className="muted-note">No rating components are available for this manager.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={[...data]} outerRadius="70%">
        <PolarGrid stroke={GRID} />
        <PolarAngleAxis dataKey="component" tick={{ fill: AXIS_TEXT, fontSize: 11 }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        <Radar dataKey="value" stroke={ACCENT} fill={ACCENT} fillOpacity={0.32} />
        <Tooltip contentStyle={tooltipStyle} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

export function FranchiseStockChart({
  data
}: {
  readonly data: readonly { readonly season: number; readonly rating: number | null }[];
}) {
  if (data.length === 0) {
    return <p className="muted-note">No season ratings are available to chart.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={[...data]} margin={{ top: 8, right: 16, bottom: 4, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey="season" tick={{ fill: AXIS_TEXT, fontSize: 11 }} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fill: AXIS_TEXT, fontSize: 11 }} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Line
          type="monotone"
          dataKey="rating"
          stroke={ACCENT}
          strokeWidth={2}
          dot={{ r: 3, fill: ACCENT }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
