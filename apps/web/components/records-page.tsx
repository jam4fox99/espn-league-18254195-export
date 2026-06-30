"use client";

import ky, { HTTPError } from "ky";
import { useCallback } from "react";
import { z } from "zod";
import { LeagueNav, MetricStrip, ProductHeader } from "@/components/product-chrome";
import { ProductLoader } from "@/components/product-loader";
import { StatusPill } from "@/components/status-pill";
import { readPublicEnv } from "@/lib/env";
import type { AlphaSession } from "@/lib/session";
import { createAlphaBearer } from "@/lib/session";

const recordRowSchema = z.object({
  recordId: z.string().min(1).optional(),
  category: z.string().default("records"),
  label: z.string(),
  value: z.union([z.string(), z.number()]),
  managerKey: z.string().optional(),
  managerName: z.string().optional(),
  teamName: z.string().optional(),
  season: z.number().int().nullable().optional(),
  detail: z.string().nullable().optional(),
  caveats: z.array(z.string()).optional()
});

const recordsResponseSchema = z.object({
  modelName: z.string().default("records_v1"),
  modelVersion: z.string().default("current"),
  rows: z.array(recordRowSchema)
});

const legacyFixtureSchema = z.object({
  dashboard: z.object({
    formula_version: z.string(),
    top_manager: z.object({ score: z.number() }).optional()
  })
});

type RecordRow = z.infer<typeof recordRowSchema>;
type RecordsResponse = z.infer<typeof recordsResponseSchema>;

export function RecordsPage({ leagueId }: { readonly leagueId: string }) {
  const load = useCallback((session: AlphaSession) => readRecords(session, leagueId), [leagueId]);

  return (
    <ProductLoader load={load}>
      {(records) => {
        const categories = groupRecords(records.rows);
        const rowCount = records.rows.length;
        return (
          <section className="product-stack">
            <LeagueNav leagueId={leagueId} />
            <ProductHeader eyebrow={records.modelName} leagueId={leagueId} title="League records">
              <StatusPill tone={rowCount > 0 ? "success" : "warning"}>
                {rowCount > 0 ? "Records loaded" : "Records pending"}
              </StatusPill>
            </ProductHeader>
            <MetricStrip
              metrics={[
                {
                  label: "Record rows",
                  value: rowCount.toString(),
                  detail: "Only source-backed record rows are displayed."
                },
                {
                  label: "Categories",
                  value: categories.length.toString(),
                  detail: "Grouped by API category for inspection."
                },
                {
                  label: "Unsupported fields",
                  value: "Caveated",
                  detail: "Championship/playoff facts are omitted unless source data marks them."
                }
              ]}
            />
            <article className="product-panel">
              <h2>Unsupported record fields</h2>
              <p>
                Championship counts and playoff splits are not shown without standings or playoff
                markers in the source snapshot.
              </p>
            </article>
            <div className="records-grid">
              {records.rows.map((row, index) => (
                <RecordCard
                  key={row.recordId ?? `${row.category}-${row.label}-${index}`}
                  row={row}
                />
              ))}
            </div>
          </section>
        );
      }}
    </ProductLoader>
  );
}

function RecordCard({ row }: { readonly row: RecordRow }) {
  const holder = row.managerName ?? row.teamName ?? "League-wide";
  const notes: string[] = [];
  if (row.detail) {
    notes.push(row.detail);
  }
  for (const caveat of row.caveats ?? []) {
    notes.push(caveat);
  }
  return (
    <article className="record-card">
      <p className="record-card__label">{titleCase(row.label)}</p>
      <p className="record-card__value">{formatValue(row.value)}</p>
      <p className="record-card__holder">
        <span className="record-card__name">{holder}</span>
        {row.season ? <span className="record-card__season">{row.season}</span> : null}
      </p>
      {notes.length > 0 ? <p className="record-card__note">{notes.join(" · ")}</p> : null}
    </article>
  );
}

async function readRecords(session: AlphaSession, leagueId: string): Promise<RecordsResponse> {
  const payload = await protectedJson(session, `v1/leagues/${leagueId}/records?version=current`);
  const records = recordsResponseSchema.safeParse(payload);
  if (records.success) {
    return records.data;
  }

  const fixture = legacyFixtureSchema.parse(payload);
  return {
    modelName: "records_v1",
    modelVersion: fixture.dashboard.formula_version,
    rows: [
      {
        recordId: "legacy-score-leader",
        category: "score",
        label: "Top retrospective score",
        value: fixture.dashboard.top_manager?.score ?? 0,
        detail: "Legacy fixture summary row; detailed records require snapshot record rows.",
        caveats: ["Championship and playoff records omitted until source data supports them."]
      }
    ]
  };
}

async function protectedJson(session: AlphaSession, path: string): Promise<unknown> {
  const client = ky.create({
    baseUrl: readPublicEnv().NEXT_PUBLIC_API_BASE_URL,
    retry: 0,
    timeout: 10000
  });

  try {
    return await client(path, {
      headers: { Authorization: `Bearer ${createAlphaBearer(session)}` }
    }).json();
  } catch (error) {
    if (error instanceof HTTPError) {
      throw new Error(`API request failed for ${path}: ${error.response.status}`);
    }
    throw error;
  }
}

function groupRecords(rows: readonly RecordRow[]): readonly {
  readonly name: string;
  readonly rows: readonly RecordRow[];
}[] {
  const categories = new Map<string, RecordRow[]>();
  for (const row of rows) {
    const categoryRows = categories.get(row.category) ?? [];
    categoryRows.push(row);
    categories.set(row.category, categoryRows);
  }
  return [...categories.entries()].map(([name, categoryRows]) => ({ name, rows: categoryRows }));
}

function titleCase(value: string): string {
  return value
    .split(/[_-]/)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function formatValue(value: string | number): string {
  return typeof value === "number"
    ? value.toLocaleString("en-US", { maximumFractionDigits: 2 })
    : value;
}
