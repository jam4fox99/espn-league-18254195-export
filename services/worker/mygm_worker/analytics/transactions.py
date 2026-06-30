from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from mygm_worker.analytics.json_tools import int_value, sorted_counts, string_value
from mygm_worker.analytics.models import (
    AcquisitionAnalytics,
    JsonObject,
    JsonValue,
    TradeAnalytics,
)

if TYPE_CHECKING:
    from mygm_worker.analytics.reader import FixtureReader


def trade_analytics(reader: FixtureReader) -> TradeAnalytics:
    summary = reader.trade_grade_summary()
    return TradeAnalytics(
        completed_trade_accept_rows=int_value(summary.get("completed_trade_accept_rows")),
        graded_rows=int_value(summary.get("graded_rows")),
        ungraded_rows=int_value(summary.get("ungraded_rows")),
        canonical_graded_trade_events=int_value(summary.get("canonical_graded_trade_groups")),
        canonical_groups_with_multiple_rows=int_value(
            summary.get("canonical_groups_with_multiple_rows")
        ),
        item_sources=_int_map(summary.get("trade_item_sources")),
        ungraded_reasons=_int_map(summary.get("ungraded_reasons")),
    )


def acquisition_analytics(reader: FixtureReader) -> AcquisitionAnalytics:
    type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    exclusion_reasons: Counter[str] = Counter()
    counted_rows = 0
    gross_rows = 0
    net_rows = 0
    bid_amounts: set[int] = set()

    for tx in reader.transaction_rows():
        tx_type = string_value(tx.get("type"))
        if tx_type not in {"WAIVER", "FREEAGENT"}:
            continue
        type_counts[tx_type] += 1
        status = string_value(tx.get("status"), "UNKNOWN") or "UNKNOWN"
        status_counts[status] += 1
        bid_amounts.add(int_value(tx.get("bidAmount")))
        if status != "EXECUTED":
            exclusion_reasons[f"status:{status}"] += 1
            continue
        add_count, drop_count = _add_drop_counts(tx)
        if add_count == 0:
            exclusion_reasons["executed_without_add"] += 1
            continue
        counted_rows += 1
        if drop_count == 0:
            gross_rows += 1
        else:
            net_rows += 1

    total_rows = sum(type_counts.values())
    return AcquisitionAnalytics(
        total_rows=total_rows,
        counted_rows=counted_rows,
        excluded_rows=total_rows - counted_rows,
        type_counts=sorted_counts(dict(type_counts)),
        status_counts=sorted_counts(dict(status_counts)),
        exclusion_reasons=sorted_counts(dict(exclusion_reasons)),
        gross_rows=gross_rows,
        net_rows=net_rows,
        faab_warning=_faab_warning(bid_amounts),
    )


def _add_drop_counts(tx: JsonObject) -> tuple[int, int]:
    add_count = 0
    drop_count = 0
    items = tx.get("items")
    if not isinstance(items, list):
        return add_count, drop_count
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "ADD":
            add_count += 1
        if item_type == "DROP":
            drop_count += 1
    return add_count, drop_count


def _faab_warning(bid_amounts: set[int]) -> str:
    if bid_amounts == {0}:
        return "FAAB context unavailable: bidAmount is always 0"
    return "FAAB context partially available"


def _int_map(value: JsonValue) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return sorted_counts({key: int_value(item) for key, item in value.items()})
