# Sample data & sheet schema

The `/data` folder contains CSV exports you can import directly into Google Sheets or Airtable to power the demo mode.

| Sheet tab | Source CSV | Description |
|-----------|------------|-------------|
| `products` | `data/sample_products.csv` | Core SKU attributes, including vendor, list price, and metal usage assumptions. |
| `orders` | `data/sample_orders.csv` | Shopify order history (120 days) with unit quantities and realized prices. |
| `inventory` | `data/sample_inventory.csv` | Multi-location available and on-hand units. |
| `locations` | `data/sample_locations.csv` | Human-readable location names. |
| `vendor_params` | `data/sample_vendor_params.csv` | Lead times and minimum order quantities (MOQ) per vendor. |
| `metal_prices` | `data/sample_metal_prices.csv` | Daily spot price per gram for supported metals (Au & Pt). |

## Importing into Google Sheets

1. Create a new Google Sheet named **Jewelry Inventory Co-Pilot**.
2. Add a tab for each dataset listed above (ensure the tab names exactly match the table).
3. From Google Sheets: *File → Import → Upload* and select the corresponding CSV, choosing "Replace data at selected cell".
4. Freeze the header row (View → Freeze) so it matches the column names consumed by the Python metrics engine.
5. Share the sheet with your Retool service account (or the email specified under *Resources → Credentials*) with edit permissions.

If you prefer Airtable, create base tables with the same column names. Retool's Airtable resource can connect to them with minimal adjustments.

## Demo mode

The included CSVs are intentionally small (<1 KB each) so that the Retool Upload component can ingest them instantly. In demo mode, simply drag the CSVs into the upload wizard—no external connectors required.
