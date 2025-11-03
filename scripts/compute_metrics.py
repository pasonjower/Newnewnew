"""Metrics engine for the Jewelry Inventory Co-Pilot MVP (standard library only)."""
from __future__ import annotations

import base64
import csv
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Optional

DEMAND_WINDOW_DAYS = 90
SERVICE_LEVEL_Z = 1.65  # 95% service level

SKU_COLUMNS = [
    "sku",
    "name",
    "vendor_id",
    "vendor_name",
    "metal",
    "grams_per_unit",
    "base_unit_cost",
    "finishing_loss_pct",
    "shrinkage_pct",
    "list_price",
    "spot_price_per_gram",
    "gross_metal_grams",
    "net_metal_grams",
    "gross_metal_cost",
    "net_metal_cost",
    "net_unit_cost",
    "unit_margin",
    "gross_margin_rate",
    "units_sold",
    "revenue",
    "on_hand_units",
    "available_units",
    "avg_daily_demand",
    "demand_std",
    "sell_through",
    "stock_to_sales_ratio",
    "weeks_of_supply",
    "safety_stock",
    "reorder_point",
    "recommended_order_qty",
    "lead_time_days",
    "moq_units",
    "target_po_date",
    "projected_stockout_date",
    "gross_margin_dollars",
    "revenue_percentile",
    "margin_percentile",
    "revenue_abc",
    "margin_abc",
    "sku_health_score",
    "rationale_tags",
]

PRIORITY_COLUMNS = [
    "sku",
    "name",
    "vendor_id",
    "vendor_name",
    "recommended_order_qty",
    "lead_time_days",
    "target_po_date",
    "projected_stockout_date",
    "gross_margin_rate",
    "weeks_of_supply",
    "sku_health_score",
    "rationale_tags",
]

DRAFT_PO_COLUMNS = [
    "vendor_id",
    "vendor_name",
    "sku",
    "name",
    "recommended_order_qty",
    "target_po_date",
    "projected_stockout_date",
    "unit_cost",
    "total_cost",
]


@dataclass
class MetricsPayload:
    sku_level: List[Dict[str, object]]
    replenish_now: List[Dict[str, object]]
    cut_defer: List[Dict[str, object]]
    double_down: List[Dict[str, object]]
    draft_pos: List[Dict[str, object]]
    kpi_summary: Dict[str, float]

    def to_dict(self) -> Dict[str, object]:
        return {
            "sku_level": self.sku_level,
            "replenish_now": self.replenish_now,
            "cut_defer": self.cut_defer,
            "double_down": self.double_down,
            "draft_pos": dicts_to_csv_base64(self.draft_pos, DRAFT_PO_COLUMNS),
            "kpi_summary": self.kpi_summary,
        }


def dicts_to_csv_base64(rows: List[Dict[str, object]], columns: List[str]) -> str:
    buffer = []
    if not rows:
        return ""
    output = csv_string(rows, columns)
    return base64.b64encode(output.encode("utf-8")).decode("utf-8")


def csv_string(rows: List[Dict[str, object]], columns: List[str]) -> str:
    from io import StringIO

    sio = StringIO()
    writer = csv.DictWriter(sio, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, "") for col in columns})
    return sio.getvalue()


def load_csv(path_or_buffer) -> List[Dict[str, str]]:
    if hasattr(path_or_buffer, "read"):
        reader = csv.DictReader(path_or_buffer.read().decode("utf-8").splitlines())
        return [dict(row) for row in reader]
    path = Path(path_or_buffer)
    with path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def latest_metal_prices(rows: List[Dict[str, str]]) -> Dict[str, float]:
    latest: Dict[str, Dict[str, object]] = {}
    for row in rows:
        metal = row.get("metal", "").strip()
        if not metal:
            continue
        spot = parse_float(row.get("spot_price_per_gram", "0"), 0.0)
        dt = parse_date(row.get("date", "1970-01-01"))
        current = latest.get(metal)
        if current is None or dt > current["date"]:
            latest[metal] = {"date": dt, "price": spot}
    return {metal: data["price"] for metal, data in latest.items()}


def compute_orders(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, object]]:
    if not rows:
        return {}
    max_date = max(parse_date(row["order_date"]) for row in rows)
    window_start = max_date - timedelta(days=DEMAND_WINDOW_DAYS)
    demand_window_days = max(1, min(DEMAND_WINDOW_DAYS, (max_date - window_start).days or DEMAND_WINDOW_DAYS))

    aggregates: Dict[str, Dict[str, object]] = {}
    for row in rows:
        order_date = parse_date(row["order_date"])
        if order_date < window_start:
            continue
        sku = row["sku"].strip()
        quantity = parse_float(row.get("quantity", "0"), 0.0)
        unit_price = parse_float(row.get("unit_price", "0"), 0.0)
        data = aggregates.setdefault(
            sku,
            {
                "units_sold": 0.0,
                "revenue": 0.0,
                "daily": {},
                "avg_daily_demand": 0.0,
                "demand_std": 0.0,
                "window_days": demand_window_days,
            },
        )
        data["units_sold"] += quantity
        data["revenue"] += quantity * unit_price
        daily = data.setdefault("daily", {})
        daily[order_date] = daily.get(order_date, 0.0) + quantity

    for sku, data in aggregates.items():
        daily_values = list(data.get("daily", {}).values())
        if daily_values:
            data["avg_daily_demand"] = mean(daily_values)
            data["demand_std"] = pstdev(daily_values) if len(daily_values) > 1 else 0.0
        if data.get("avg_daily_demand", 0) == 0 and data["units_sold"] > 0:
            data["avg_daily_demand"] = data["units_sold"] / data["window_days"]
    return aggregates


def compute_inventory(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, float]]:
    totals: Dict[str, Dict[str, float]] = {}
    for row in rows:
        sku = row["sku"].strip()
        data = totals.setdefault(sku, {"on_hand": 0.0, "available": 0.0})
        data["on_hand"] += parse_float(row.get("on_hand", "0"), 0.0)
        data["available"] += parse_float(row.get("available", "0"), 0.0)
    return totals


def compute_vendor_params(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, float]]:
    params = {}
    for row in rows:
        vendor_id = row.get("vendor_id", "").strip()
        if not vendor_id:
            continue
        params[vendor_id] = {
            "vendor_name": row.get("vendor_name", ""),
            "lead_time_days": parse_float(row.get("lead_time_days", "14"), 14.0),
            "moq_units": parse_float(row.get("moq_units", "1"), 1.0),
        }
    return params


def enrich_products(
    rows: List[Dict[str, str]],
    metal_prices: Dict[str, float],
) -> Dict[str, Dict[str, object]]:
    products = {}
    for row in rows:
        sku = row.get("sku", "").strip()
        if not sku:
            continue
        grams = parse_float(row.get("grams_per_unit", "0"), 0.0)
        base_cost = parse_float(row.get("base_unit_cost", "0"), 0.0)
        finishing_loss = parse_float(row.get("finishing_loss_pct", "0"), 0.0)
        shrinkage = parse_float(row.get("shrinkage_pct", "0"), 0.0)
        list_price = parse_float(row.get("list_price", "0"), 0.0)
        metal = row.get("metal", "").strip()
        spot_price = metal_prices.get(metal, 0.0)
        gross_grams = grams * (1 + finishing_loss / 100)
        net_grams = gross_grams * (1 - shrinkage / 100)
        gross_cost = gross_grams * spot_price
        net_cost = net_grams * spot_price
        net_unit_cost = base_cost + net_cost
        unit_margin = list_price - net_unit_cost
        gross_margin_rate = unit_margin / list_price if list_price else 0.0
        products[sku] = {
            "sku": sku,
            "name": row.get("name", ""),
            "vendor_id": row.get("vendor_id", ""),
            "vendor_name": row.get("vendor_name", ""),
            "metal": metal,
            "grams_per_unit": grams,
            "base_unit_cost": base_cost,
            "finishing_loss_pct": finishing_loss,
            "shrinkage_pct": shrinkage,
            "list_price": list_price,
            "spot_price_per_gram": spot_price,
            "gross_metal_grams": gross_grams,
            "net_metal_grams": net_grams,
            "gross_metal_cost": gross_cost,
            "net_metal_cost": net_cost,
            "net_unit_cost": net_unit_cost,
            "unit_margin": unit_margin,
            "gross_margin_rate": gross_margin_rate,
        }
    return products


def classify_abc(cumulative_share: float) -> str:
    if cumulative_share <= 0.8:
        return "A"
    if cumulative_share <= 0.95:
        return "B"
    return "C"


def round_to_moq(value: float, moq: float) -> float:
    if value <= 0:
        return 0.0
    if moq <= 0:
        return round(value, 2)
    return math.ceil(value / moq) * moq


def format_date(value: Optional[date]) -> str:
    return value.isoformat() if isinstance(value, date) else ""


def compute_health_score(record: Dict[str, object]) -> float:
    reorder_point = float(record.get("reorder_point", 0.0))
    on_hand = float(record.get("on_hand_units", 0.0))
    margin_rate = float(record.get("gross_margin_rate", 0.0))
    revenue_percentile = float(record.get("revenue_percentile", 0.0))
    weeks_of_supply = float(record.get("weeks_of_supply", 0.0))
    revenue_abc = record.get("revenue_abc", "C")
    margin_abc = record.get("margin_abc", "C")

    coverage_ratio = 1.0 if reorder_point <= 0 else on_hand / reorder_point if reorder_point else 1.0
    coverage_score = 100 - min(abs(1 - coverage_ratio) * 100, 70)
    margin_score = max(min((margin_rate / 0.6) * 100, 100), 0)
    velocity_score = revenue_percentile * 100

    if revenue_abc in {"A", "B"} and margin_abc in {"A", "B"}:
        abc_score = 100
    elif revenue_abc in {"A", "B"} or margin_abc in {"A", "B"}:
        abc_score = 70
    else:
        abc_score = 30

    aging_penalty = max(0.0, weeks_of_supply - 12) * 4

    health = (
        0.3 * coverage_score
        + 0.25 * margin_score
        + 0.2 * velocity_score
        + 0.15 * abc_score
        - 0.1 * aging_penalty
    )
    return max(min(health, 100), 0)


def derive_rationale(record: Dict[str, object]) -> str:
    reasons: List[str] = []
    if float(record.get("recommended_order_qty", 0.0)) > 0:
        reasons.append("Below reorder point")
    if float(record.get("gross_margin_rate", 0.0)) < 0:
        reasons.append("Negative margin")
    if float(record.get("weeks_of_supply", 0.0)) > 16:
        reasons.append("High WOS")
    if (
        float(record.get("weeks_of_supply", 0.0)) < 3
        and float(record.get("gross_margin_rate", 0.0)) >= 0.35
    ):
        reasons.append("High velocity & margin")
    if float(record.get("sell_through", 0.0)) < 0.2:
        reasons.append("Low sell-through")
    return ", ".join(sorted(set(reasons)))


def build_metrics(
    products: Dict[str, Dict[str, object]],
    orders: Dict[str, Dict[str, object]],
    inventory: Dict[str, Dict[str, float]],
    vendor_params: Dict[str, Dict[str, float]],
    today: date,
) -> List[Dict[str, object]]:
    metrics: List[Dict[str, object]] = []

    for sku, product in products.items():
        order_stats = orders.get(sku, {})
        inventory_stats = inventory.get(sku, {"on_hand": 0.0, "available": 0.0})
        vendor = vendor_params.get(product.get("vendor_id", ""), {})

        lead_time = vendor.get("lead_time_days", 14.0)
        moq = vendor.get("moq_units", 1.0)
        units_sold = float(order_stats.get("units_sold", 0.0))
        revenue = float(order_stats.get("revenue", 0.0))
        avg_daily_demand = float(order_stats.get("avg_daily_demand", 0.0))
        demand_std = float(order_stats.get("demand_std", 0.0))
        on_hand = float(inventory_stats.get("on_hand", 0.0))
        available = float(inventory_stats.get("available", 0.0))

        sell_through = units_sold / (units_sold + on_hand) if (units_sold + on_hand) > 0 else 0.0
        stock_to_sales = on_hand / avg_daily_demand if avg_daily_demand > 0 else 0.0
        weeks_of_supply = stock_to_sales / 7 if avg_daily_demand > 0 else 0.0
        safety_stock = SERVICE_LEVEL_Z * demand_std * math.sqrt(max(lead_time, 1))
        reorder_point = lead_time * avg_daily_demand + safety_stock
        recommended_qty = round_to_moq(max(reorder_point - on_hand, 0.0), moq)
        projected_stockout = today + timedelta(days=on_hand / avg_daily_demand) if avg_daily_demand > 0 and on_hand > 0 else None
        target_po_date = today + timedelta(days=int(math.ceil(lead_time)))

        gross_margin_dollars = product["unit_margin"] * units_sold

        record = {
            **product,
            "units_sold": round(units_sold, 2),
            "revenue": round(revenue, 2),
            "on_hand_units": round(on_hand, 2),
            "available_units": round(available, 2),
            "avg_daily_demand": round(avg_daily_demand, 4),
            "demand_std": round(demand_std, 4),
            "sell_through": round(sell_through, 4),
            "stock_to_sales_ratio": round(stock_to_sales, 4),
            "weeks_of_supply": round(weeks_of_supply, 4),
            "safety_stock": round(safety_stock, 4),
            "reorder_point": round(reorder_point, 4),
            "recommended_order_qty": round(recommended_qty, 2),
            "lead_time_days": round(lead_time, 2),
            "moq_units": round(moq, 2),
            "target_po_date": format_date(target_po_date),
            "projected_stockout_date": format_date(projected_stockout),
            "gross_margin_dollars": round(gross_margin_dollars, 2),
            "vendor_name": vendor.get("vendor_name", product.get("vendor_name", "")) or product.get("vendor_name", ""),
            "revenue_percentile": 0.0,
            "margin_percentile": 0.0,
            "revenue_abc": "C",
            "margin_abc": "C",
            "sku_health_score": 0.0,
            "rationale_tags": "",
        }
        metrics.append(record)
    return metrics


def apply_percentiles(metrics: List[Dict[str, object]], key: str, percentile_key: str) -> None:
    if not metrics:
        return
    sorted_records = sorted(metrics, key=lambda r: float(r.get(key, 0.0)))
    n = len(sorted_records)
    for idx, record in enumerate(sorted_records, start=1):
        record[percentile_key] = idx / n


def apply_abc(metrics: List[Dict[str, object]], value_key: str, abc_key: str) -> None:
    total = sum(float(record.get(value_key, 0.0)) for record in metrics)
    if total <= 0:
        for record in metrics:
            record[abc_key] = "C"
        return
    running = 0.0
    for record in sorted(metrics, key=lambda r: float(r.get(value_key, 0.0)), reverse=True):
        running += float(record.get(value_key, 0.0))
        share = running / total
        record[abc_key] = classify_abc(share)


def finalize_records(metrics: List[Dict[str, object]]) -> None:
    apply_percentiles(metrics, "revenue", "revenue_percentile")
    apply_percentiles(metrics, "gross_margin_dollars", "margin_percentile")
    apply_abc(metrics, "revenue", "revenue_abc")
    apply_abc(metrics, "gross_margin_dollars", "margin_abc")

    for record in metrics:
        record["sku_health_score"] = round(compute_health_score(record), 2)
        record["rationale_tags"] = derive_rationale(record)
        record["gross_margin_rate"] = round(float(record.get("gross_margin_rate", 0.0)), 4)


def build_prioritized_views(metrics: List[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    replenish = [m for m in metrics if m["recommended_order_qty"] > 0 and m["avg_daily_demand"] > 0]
    cut_defer = [
        m
        for m in metrics
        if m["gross_margin_rate"] < 0
        or m["weeks_of_supply"] > 16
        or (m["revenue_percentile"] < 0.2 and m["gross_margin_rate"] < 0.15)
    ]
    double_down = [
        m
        for m in metrics
        if m["weeks_of_supply"] < 3 and m["gross_margin_rate"] >= 0.35 and m["revenue_percentile"] >= 0.6
    ]

    for lst in (replenish, cut_defer, double_down):
        lst.sort(key=lambda r: r["sku_health_score"], reverse=True)

    draft_pos = []
    for record in replenish:
        draft_pos.append(
            {
                "vendor_id": record.get("vendor_id", ""),
                "vendor_name": record.get("vendor_name", ""),
                "sku": record.get("sku", ""),
                "name": record.get("name", ""),
                "recommended_order_qty": record.get("recommended_order_qty", 0.0),
                "target_po_date": record.get("target_po_date", ""),
                "projected_stockout_date": record.get("projected_stockout_date", ""),
                "unit_cost": round(float(record.get("net_unit_cost", 0.0)), 2),
                "total_cost": round(float(record.get("net_unit_cost", 0.0)) * float(record.get("recommended_order_qty", 0.0)), 2),
            }
        )
    draft_pos.sort(key=lambda r: (r["vendor_id"], r["sku"]))

    return {
        "replenish_now": [project_columns(r, PRIORITY_COLUMNS) for r in replenish],
        "cut_defer": [project_columns(r, PRIORITY_COLUMNS) for r in cut_defer],
        "double_down": [project_columns(r, PRIORITY_COLUMNS) for r in double_down],
        "draft_pos": draft_pos,
    }


def project_columns(record: Dict[str, object], columns: List[str]) -> Dict[str, object]:
    return {column: record.get(column, "") for column in columns}


def compute_kpis(metrics: List[Dict[str, object]]) -> Dict[str, float]:
    total_units_sold = sum(float(m.get("units_sold", 0.0)) for m in metrics)
    total_on_hand = sum(float(m.get("on_hand_units", 0.0)) for m in metrics)
    average_inventory = (total_on_hand + max(total_on_hand - total_units_sold, 0.0)) / 2 or 1
    turnover = total_units_sold / average_inventory if average_inventory else 0.0

    total_avg_daily = sum(float(m.get("avg_daily_demand", 0.0)) for m in metrics) or 1
    days_on_hand = total_on_hand / total_avg_daily

    percent_in_stock = (
        sum(1 for m in metrics if float(m.get("on_hand_units", 0.0)) > 0) / len(metrics) * 100 if metrics else 0
    )

    gross_margin = sum(float(m.get("gross_margin_dollars", 0.0)) for m in metrics)
    aged_inventory = sum(
        float(m.get("on_hand_units", 0.0)) * float(m.get("net_unit_cost", 0.0))
        for m in metrics
        if float(m.get("weeks_of_supply", 0.0)) > 12
    )

    return {
        "inventory_turnover": round(turnover, 2),
        "days_on_hand": round(days_on_hand, 1),
        "percent_in_stock": round(percent_in_stock, 1),
        "gross_margin_dollars": round(gross_margin, 2),
        "aged_inventory_value": round(aged_inventory, 2),
    }


def run_all_metrics(
    *,
    orders_csv,
    products_csv,
    inventory_csv,
    locations_csv,  # Included for parity with Shopify exports; not used in current calcs
    vendor_params_csv,
    metal_prices_csv,
    today: Optional[date] = None,
) -> MetricsPayload:
    today = today or date.today()

    orders_data = compute_orders(load_csv(orders_csv))
    inventory_data = compute_inventory(load_csv(inventory_csv))
    vendor_data = compute_vendor_params(load_csv(vendor_params_csv))
    metal_price_lookup = latest_metal_prices(load_csv(metal_prices_csv))
    products = enrich_products(load_csv(products_csv), metal_price_lookup)

    metrics = build_metrics(products, orders_data, inventory_data, vendor_data, today)
    finalize_records(metrics)
    views = build_prioritized_views(metrics)
    kpis = compute_kpis(metrics)

    return MetricsPayload(
        sku_level=[project_columns(record, SKU_COLUMNS) for record in metrics],
        replenish_now=views["replenish_now"],
        cut_defer=views["cut_defer"],
        double_down=views["double_down"],
        draft_pos=views["draft_pos"],
        kpi_summary=kpis,
    )


def run_from_paths(data_paths: Dict[str, Path]) -> MetricsPayload:
    return run_all_metrics(
        orders_csv=data_paths["orders"],
        products_csv=data_paths["products"],
        inventory_csv=data_paths["inventory"],
        locations_csv=data_paths["locations"],
        vendor_params_csv=data_paths["vendor_params"],
        metal_prices_csv=data_paths["metal_prices"],
    )


def write_csv(path: Path, rows: List[Dict[str, object]], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def write_outputs(payload: MetricsPayload, output_dir: Path) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    sku_metrics_path = output_dir / "sku_metrics.csv"
    write_csv(sku_metrics_path, payload.sku_level, SKU_COLUMNS)
    paths["sku_metrics"] = sku_metrics_path

    for name, rows in {
        "replenish_now": payload.replenish_now,
        "cut_defer": payload.cut_defer,
        "double_down": payload.double_down,
        "draft_purchase_orders": payload.draft_pos,
    }.items():
        columns = DRAFT_PO_COLUMNS if name == "draft_purchase_orders" else PRIORITY_COLUMNS
        path = output_dir / f"{name}.csv"
        write_csv(path, rows, columns)
        paths[name] = path

    kpi_path = output_dir / "kpi_summary.json"
    with kpi_path.open("w", encoding="utf-8") as fh:
        json.dump(payload.kpi_summary, fh, indent=2)
    paths["kpi_summary"] = kpi_path

    return paths


def cli(argv: Optional[Iterable[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Compute inventory planning metrics.")
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--products", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--locations", type=Path, required=True)
    parser.add_argument("--vendor-params", type=Path, required=True)
    parser.add_argument("--metal-prices", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    payload = run_from_paths(
        {
            "orders": args.orders,
            "products": args.products,
            "inventory": args.inventory,
            "locations": args.locations,
            "vendor_params": args.vendor_params,
            "metal_prices": args.metal_prices,
        }
    )
    write_outputs(payload, args.output_dir)


if __name__ == "__main__":
    cli()
