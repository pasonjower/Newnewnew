"""Run the metrics engine against the bundled sample data."""
from __future__ import annotations

import json
from pathlib import Path

from compute_metrics import run_from_paths, write_outputs

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "outputs"


def main() -> None:
    payload = run_from_paths(
        {
            "orders": DATA_DIR / "sample_orders.csv",
            "products": DATA_DIR / "sample_products.csv",
            "inventory": DATA_DIR / "sample_inventory.csv",
            "locations": DATA_DIR / "sample_locations.csv",
            "vendor_params": DATA_DIR / "sample_vendor_params.csv",
            "metal_prices": DATA_DIR / "sample_metal_prices.csv",
        }
    )
    paths = write_outputs(payload, OUTPUT_DIR)

    print("Jewelry Inventory Co-Pilot demo refresh complete.\n")
    print("Key KPIs:")
    for key, value in payload.kpi_summary.items():
        print(f"  - {key}: {value}")

    print("\nPrioritized lists written to:")
    for label in ["replenish_now", "cut_defer", "double_down", "draft_purchase_orders"]:
        print(f"  - {label}: {paths[label]}")

    summary_path = OUTPUT_DIR / "metrics_payload.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(payload.to_dict(), fh, indent=2, default=str)
    print(f"\nFull payload serialized to: {summary_path}")


if __name__ == "__main__":
    main()
