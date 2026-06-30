"use client";

import { Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { type ControlOption, MultiSelect, Select } from "@/components/controls/select";

export type { ControlOption };

export type Facet<Row> = {
  readonly key: string;
  readonly label: string;
  readonly options: readonly ControlOption[];
  /** The facet values present on a row (a row matches if it shares any selected value). */
  readonly valuesOf: (row: Row) => readonly string[];
};

export type SortOption<Row> = {
  readonly value: string;
  readonly label: string;
  readonly compare: (left: Row, right: Row) => number;
};

export type FilterState = Record<string, readonly string[]>;

/** The non-generic surface the FilterBar renders from. */
export type FacetController = {
  readonly selected: FilterState;
  readonly toggleValue: (key: string, value: string) => void;
  readonly clearAll: () => void;
  readonly search: string;
  readonly setSearch: (value: string) => void;
  readonly sort: string;
  readonly setSort: (value: string) => void;
  readonly count: number;
};

/**
 * Pure facet+search predicate: OR within a facet, AND across facets. Exported so a
 * surface can apply one controller's state to several differently-typed row lists.
 */
export function filterRows<Row>(
  rows: readonly Row[],
  facets: readonly Facet<Row>[],
  selected: FilterState,
  search: string,
  searchText?: (row: Row) => string
): readonly Row[] {
  const query = search.trim().toLowerCase();
  return rows.filter((row) => {
    for (const facet of facets) {
      const picks = selected[facet.key] ?? [];
      if (picks.length === 0) {
        continue;
      }
      const values = facet.valuesOf(row);
      if (!picks.some((pick) => values.includes(pick))) {
        return false;
      }
    }
    if (query.length > 0 && searchText) {
      return searchText(row).toLowerCase().includes(query);
    }
    return true;
  });
}

/**
 * Generic faceted filter state: OR within a facet, AND across facets, plus a
 * free-text search and a sort. Returns the filtered+sorted rows and the controller
 * surface a `<FilterBar>` renders.
 */
export function useFacetFilter<Row>(opts: {
  readonly rows: readonly Row[];
  readonly facets: readonly Facet<Row>[];
  readonly sorts: readonly SortOption<Row>[];
  readonly searchText?: (row: Row) => string;
}): FacetController & { readonly filtered: readonly Row[] } {
  const { rows, facets, sorts, searchText } = opts;
  const [selected, setSelected] = useState<FilterState>({});
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState(sorts[0]?.value ?? "");

  const filtered = useMemo(() => {
    const matched = filterRows(rows, facets, selected, search, searchText);
    const sorter = sorts.find((option) => option.value === sort);
    return sorter ? [...matched].sort(sorter.compare) : matched;
  }, [rows, facets, sorts, selected, search, sort, searchText]);

  return {
    selected,
    toggleValue: (key, value) =>
      setSelected((prev) => {
        const current = prev[key] ?? [];
        const next = current.includes(value)
          ? current.filter((item) => item !== value)
          : [...current, value];
        return { ...prev, [key]: next };
      }),
    clearAll: () => setSelected({}),
    search,
    setSearch,
    sort,
    setSort,
    count: filtered.length,
    filtered
  };
}

export function FilterBar<Row>({
  facets,
  sorts,
  controller,
  total,
  searchPlaceholder = "Search…"
}: {
  readonly facets: readonly Facet<Row>[];
  readonly sorts: readonly SortOption<Row>[];
  readonly controller: FacetController;
  readonly total: number;
  readonly searchPlaceholder?: string;
}) {
  const chips = facets.flatMap((facet) =>
    (controller.selected[facet.key] ?? []).map((value) => ({
      facet,
      value,
      label: facet.options.find((option) => option.value === value)?.label ?? value
    }))
  );
  return (
    <section className="filter-bar product-panel">
      <div className="filter-bar__controls">
        <label className="filter-search">
          <Search aria-hidden="true" size={15} />
          <input
            onChange={(event) => controller.setSearch(event.target.value)}
            placeholder={searchPlaceholder}
            type="search"
            value={controller.search}
          />
        </label>
        {facets.map((facet) => (
          <div className="filter-facet" key={facet.key}>
            <span className="filter-facet__label">{facet.label}</span>
            <MultiSelect
              ariaLabel={`Filter by ${facet.label}`}
              onToggle={(value) => controller.toggleValue(facet.key, value)}
              options={facet.options}
              placeholder="Any"
              values={controller.selected[facet.key] ?? []}
            />
          </div>
        ))}
        {sorts.length > 0 ? (
          <div className="filter-facet">
            <span className="filter-facet__label">Sort</span>
            <Select
              ariaLabel="Sort results"
              onChange={controller.setSort}
              options={sorts.map((option) => ({ value: option.value, label: option.label }))}
              value={controller.sort}
            />
          </div>
        ) : null}
      </div>
      {chips.length > 0 ? (
        <div className="filter-bar__chips">
          {chips.map((chip) => (
            <button
              className="filter-chip"
              key={`${chip.facet.key}:${chip.value}`}
              onClick={() => controller.toggleValue(chip.facet.key, chip.value)}
              type="button"
            >
              <span className="filter-chip__facet">{chip.facet.label}</span>
              <span className="filter-chip__value">{chip.label}</span>
              <X aria-hidden="true" size={12} />
            </button>
          ))}
          <button
            className="filter-chip filter-chip--clear"
            onClick={controller.clearAll}
            type="button"
          >
            Clear all
          </button>
        </div>
      ) : null}
      <p className="filter-bar__count">
        <b>{controller.count}</b> of {total}
      </p>
    </section>
  );
}
