"use client";

import { Activity, ListFilter, TrendingDown, TrendingUp, Zap } from "lucide-react";
import type { ControlOption } from "@/components/controls";
import { useManagerLogo } from "@/components/manager-logos-provider";
import { StatusPill } from "@/components/status-pill";
import { TeamEmblem } from "@/components/team-emblem";
import { PlayerChip } from "@/components/trades-page-parts";
import {
  type DetailState,
  formatSigned,
  managersForRow,
  numberField,
  playerObjects,
  rowCaveats,
  type SnapshotRow,
  stringField
} from "@/components/transaction-page-utils";
import type { WaiverSuperlativeCard, WaiverSuperlativeSeason } from "@/lib/product-api";

const ROW_CAP = 60;
const TYPE_LABELS: Record<string, string> = { WAIVER: "Waiver", FREEAGENT: "Free agent" };

export function MoveTable({
  onSelect,
  rows,
  selectedId
}: {
  readonly onSelect: (moveId: string) => void;
  readonly rows: readonly SnapshotRow[];
  readonly selectedId: string;
}) {
  const logoFor = useManagerLogo();
  const capped = rows.slice(0, ROW_CAP);
  return (
    <div className="product-panel">
      <p className="section-kicker">
        <ListFilter aria-hidden="true" size={14} /> Transactions
      </p>
      <div className="move-list">
        {capped.map((row) => {
          const id = moveId(row);
          const added = playerObjects(row, ["addedPlayers", "adds"]);
          const dropped = playerObjects(row, ["droppedPlayers", "drops"]);
          return (
            <button
              key={id}
              type="button"
              className={`move-row${selectedId === id ? " is-selected" : ""}`}
              onClick={() => onSelect(id)}
            >
              <div className="move-row__head">
                <span className="move-row__who">
                  <TeamEmblem
                    logo={logoFor(managersForRow(row)[0]?.value, numberField(row, "season"))}
                    name={managerEmblemName(row)}
                    size={22}
                  />
                  <span className="move-manager">{managerLine(row)}</span>
                </span>
                <span className="move-type">{transactionType(row)}</span>
              </div>
              <ul className="player-list">
                {added.slice(0, 2).map((asset) => (
                  <PlayerChip key={`a-${asset.name}`} asset={asset} variant="add" />
                ))}
                {dropped.slice(0, 2).map((asset) => (
                  <PlayerChip key={`d-${asset.name}`} asset={asset} variant="drop" />
                ))}
              </ul>
              <div className="move-row__foot">
                <span className="stat-pill">
                  Net <b>{formatSigned(netPoints(row))}</b>
                </span>
                {numberField(row, "dropRegret") !== undefined ? (
                  <span className="stat-pill">
                    Drop regret <b>{formatSigned(numberField(row, "dropRegret"))}</b>
                  </span>
                ) : null}
              </div>
            </button>
          );
        })}
      </div>
      {rows.length === 0 ? (
        <div className="empty-state">
          <p>No waiver or free-agent moves match the selected filters.</p>
        </div>
      ) : null}
      {rows.length > ROW_CAP ? (
        <p className="muted-note">
          Showing the first {ROW_CAP} of {rows.length.toLocaleString("en-US")} moves — refine the
          filters to narrow this list.
        </p>
      ) : null}
    </div>
  );
}

export function MoveDetail({
  detail,
  fallback
}: {
  readonly detail: DetailState;
  readonly fallback: SnapshotRow | undefined;
}) {
  const logoFor = useManagerLogo();
  const row = detail.kind === "loaded" ? detail.item : fallback;
  if (row === undefined) {
    return (
      <aside className="product-panel">
        <StatusPill tone="warning">No move selected</StatusPill>
        <p>Select a transaction to inspect add/drop points and caveats.</p>
      </aside>
    );
  }

  const added = playerObjects(row, ["addedPlayers", "adds"]);
  const dropped = playerObjects(row, ["droppedPlayers", "drops"]);
  const caveats = rowCaveats(row);

  return (
    <aside className="product-panel">
      <p className="section-kicker">Detail</p>
      <div className="move-detail__head">
        <TeamEmblem
          logo={logoFor(managersForRow(row)[0]?.value, numberField(row, "season"))}
          name={managerEmblemName(row)}
          size={34}
        />
        <h2 className="trade-card__title">{managerLine(row)}</h2>
      </div>
      <div className="stat-row">
        <span className="stat-pill">{transactionType(row)}</span>
        <span className="stat-pill">
          Net <b>{formatSigned(netPoints(row))}</b>
        </span>
        {numberField(row, "dropRegret") !== undefined ? (
          <span className="stat-pill">
            Drop regret <b>{formatSigned(numberField(row, "dropRegret"))}</b>
          </span>
        ) : null}
      </div>

      <div className="add-drop">
        <div>
          <p className="section-kicker">
            <TrendingUp aria-hidden="true" size={13} /> Added
          </p>
          {added.length > 0 ? (
            <ul className="player-list">
              {added.map((asset) => (
                <PlayerChip key={asset.name} asset={asset} variant="add" />
              ))}
            </ul>
          ) : (
            <p className="muted-note">No add recorded.</p>
          )}
        </div>
        <div>
          <p className="section-kicker">
            <TrendingDown aria-hidden="true" size={13} /> Dropped
          </p>
          {dropped.length > 0 ? (
            <ul className="player-list">
              {dropped.map((asset) => (
                <PlayerChip key={asset.name} asset={asset} variant="drop" />
              ))}
            </ul>
          ) : (
            <p className="muted-note">No drop recorded.</p>
          )}
        </div>
      </div>

      {caveats.length > 0 ? (
        <ul className="plain-list">
          {caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      ) : null}
      {detail.kind === "loading" ? (
        <p className="notice-line">Loading selected transaction detail.</p>
      ) : null}
      {detail.kind === "error" ? <p className="form-error">{detail.message}</p> : null}
    </aside>
  );
}

export function transactionTypeOptions(rows: readonly SnapshotRow[]): readonly ControlOption[] {
  return [...new Set(rows.map(transactionType))]
    .sort()
    .map((type) => ({ value: type, label: TYPE_LABELS[type] ?? type }));
}

export function transactionTypeOf(row: SnapshotRow): string {
  return transactionType(row);
}

// Facet values for the Add/Drop filter: a row can carry both an add and a drop.
export function waiverAddDropValues(row: SnapshotRow): readonly string[] {
  const values: string[] = [];
  if (playerObjects(row, ["addedPlayers", "adds"]).length > 0) {
    values.push("add");
  }
  if (playerObjects(row, ["droppedPlayers", "drops"]).length > 0) {
    values.push("drop");
  }
  return values;
}

// Free-text haystack for a move: the manager, team, and every added/dropped player.
export function waiverSearchText(row: SnapshotRow): string {
  const players = [
    ...playerObjects(row, ["addedPlayers", "adds"]),
    ...playerObjects(row, ["droppedPlayers", "drops"])
  ].map((asset) => asset.name);
  return [managerLine(row), ...players].join(" ");
}

export function firstMoveId(rows: readonly SnapshotRow[]): string {
  const row = rows[0];
  return row === undefined ? "" : moveId(row);
}

export function moveId(row: SnapshotRow): string {
  return stringField(row, "moveId") ?? stringField(row, "id") ?? "move";
}

function transactionType(row: SnapshotRow): string {
  return stringField(row, "transactionType") ?? "WAIVER";
}

export function WaiverSuperlativeHeader({
  season,
  data
}: {
  readonly season: string;
  readonly data: WaiverSuperlativeSeason | undefined;
}) {
  if (data === undefined) {
    return null;
  }
  return (
    <section className="superlative-strip">
      <SuperlativeCard
        card={data.bestPickup}
        icon={TrendingUp}
        label="Best Pickup"
        season={season}
        tone="good"
      />
      <SuperlativeCard
        card={data.worstDrop}
        icon={TrendingDown}
        label="Worst Drop"
        season={season}
        tone="bad"
      />
      <SuperlativeCard
        card={data.bestWireValue}
        icon={Zap}
        label="Best FA Value (VOR)"
        season={season}
        tone="good"
      />
      <SuperlativeCard
        card={data.mostActive}
        icon={Activity}
        label="Most Active"
        season={season}
        tone="neutral"
      />
    </section>
  );
}

function SuperlativeCard({
  card,
  icon: Icon,
  label,
  season,
  tone
}: {
  readonly card: WaiverSuperlativeCard | null | undefined;
  readonly icon: typeof Zap;
  readonly label: string;
  readonly season: string;
  readonly tone: string;
}) {
  return (
    <article className={`superlative-card superlative-card--${tone}`}>
      <p className="superlative-card__label">
        <Icon aria-hidden="true" size={13} /> {label}
      </p>
      {card ? (
        <>
          <p className="superlative-card__name">{card.displayName}</p>
          <p className="superlative-card__detail">
            {card.player || `${card.count ?? 0} moves`}
            {card.value !== undefined ? <b> · {card.value.toFixed(1)}</b> : null}
          </p>
        </>
      ) : (
        <p className="superlative-card__detail muted-note">No {season} qualifier</p>
      )}
    </article>
  );
}

function netPoints(row: SnapshotRow): number | undefined {
  return (
    numberField(row, "netPoints") ??
    numberField(row, "netPointDelta") ??
    numberField(row, "pointDelta")
  );
}

function managerLine(row: SnapshotRow): string {
  const manager = managersForRow(row)[0]?.label ?? stringField(row, "managerName") ?? "Manager";
  const team = stringField(row, "teamName");
  return team ? `${manager} · ${team}` : manager;
}

// Resolved name for the monogram emblem — team name when present, else manager.
function managerEmblemName(row: SnapshotRow): string {
  return (
    stringField(row, "teamName") ??
    managersForRow(row)[0]?.label ??
    stringField(row, "managerName") ??
    "Manager"
  );
}
