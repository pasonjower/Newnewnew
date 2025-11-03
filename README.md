# Jewelry Inventory Co-Pilot

Jewelry Inventory Co-Pilot is a lightweight supply-planning MVP that pairs a Retool front-end with Google Sheets storage and a Python metrics engine. The goal is to help independent jewelry brands understand when to replenish, cut, or double-down on SKUs by ingesting Shopify exports alongside vendor and metal pricing data.

## What you get

- **Upload wizard** for Shopify CSVs or connected Google Sheets tabs covering orders, products, inventory, and locations.
- **Interactive dashboards** with core KPIs: Inventory Turnover, Days on Hand (DOH), % In-Stock, Gross Margin Dollars, and aged inventory exposure.
- **Prioritized SKU call-to-actions**: Replenish Now, Cut/Defer, and Double-Down lists recalculated on demand.
- **Metal-aware costing** that distinguishes gross vs. net metal usage (shrinkage + finishing loss), and recalculates margin per SKU from daily spot prices.
- **Draft PO CSV export** grouped by vendor to accelerate purchasing conversations.
- **Demo mode** driven by the sample data in this repository so stakeholders can explore without connecting live systems.

The stack intentionally avoids custom infrastructure: Retool handles UI/auth, Google Sheets (or Airtable) acts as the source of truth, and a Python script (which Retool can execute via Workflows or Query Library) performs all calculations.

## Repository layout

```
.
├── data/                # Seed CSVs for demo mode and initial sheet population
├── docs/                # Deployment, calculation, and UI build instructions
├── outputs/             # Generated artifacts (e.g., draft purchase orders)
├── scripts/             # Python metric engine + demo runner
└── README.md            # You are here
```

## Quickstart (local demo)

1. Install Python 3.10+ and create a virtual environment.
2. Install the only runtime dependency:

   ```bash
   pip install -r scripts/requirements.txt
   ```

3. Run the demo driver to recompute KPIs and generate replenishment exports from the sample data:

   ```bash
   python scripts/demo_runner.py
   ```

   The command writes refreshed analytics to `outputs/` and prints summary stats to the console.

4. Open the generated CSVs (Replenish, Cut/Defer, Double-Down, Draft PO) to explore the insights your Retool UI will surface.

## Deploying the MVP

1. **Populate Google Sheets** – follow [`docs/sample_data.md`](docs/sample_data.md) to mirror the seed tables into your preferred datastore.
2. **Stand up the Retool app** – [`docs/retool_app.md`](docs/retool_app.md) walks through configuring authentication, file uploads, dashboards, editable grids, and exports.
3. **Connect the metrics engine** – use a Retool Workflow or Python Query pointed at the code in [`scripts/compute_metrics.py`](scripts/compute_metrics.py). The script is idempotent and accepts either file uploads or sheet IDs.
4. **Validate with demo mode** – by default, the Retool app can load the sample CSVs so product, design, and ops stakeholders can explore without live Shopify credentials.

## Updating metrics after data edits

Whenever vendors adjust lead times, MOQs, or metal prices directly in Google Sheets, trigger the "Recompute Metrics" workflow. Retool will:

1. Pull the latest sheet ranges.
2. Call the `run_all_metrics` entrypoint in `compute_metrics.py`.
3. Write updated KPI tables back into staging tabs for visualization, and produce new download links for the prioritized SKU lists and draft POs.

This keeps planning conversations aligned with the freshest inventory and cost data while avoiding manual spreadsheet gymnastics.

## License

This repository is provided as an internal accelerator. Adapt freely for commercial or personal use.
