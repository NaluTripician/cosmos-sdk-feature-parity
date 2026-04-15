# Cosmos DB SDK Feature Parity Dashboard

A private dashboard tracking feature parity across all Azure Cosmos DB NoSQL SDKs.

## SDKs Tracked

| SDK | Package | Repository |
|-----|---------|------------|
| .NET | `Microsoft.Azure.Cosmos` | [Azure/azure-cosmos-dotnet-v3](https://github.com/Azure/azure-cosmos-dotnet-v3) |
| Java | `azure-cosmos` | [Azure/azure-sdk-for-java](https://github.com/Azure/azure-sdk-for-java) |
| Python | `azure-cosmos` | [Azure/azure-sdk-for-python](https://github.com/Azure/azure-sdk-for-python) |
| Go | `azcosmos` | [Azure/azure-sdk-for-go](https://github.com/Azure/azure-sdk-for-go) |
| Rust | `azure_data_cosmos` | [Azure/azure-sdk-for-rust](https://github.com/Azure/azure-sdk-for-rust) |

## How It Works

1. **`data/features.yaml`** — Curated feature × SDK parity matrix (source of truth)
2. **`data/sdks.yaml`** — SDK metadata (repos, changelog paths, versions)
3. **`scripts/`** — Python scripts to scrape changelogs and detect changes
4. **`site/`** — Static React dashboard (deployed to GitHub Pages)
5. **`.github/workflows/`** — Weekly cron to update data and redeploy

## Quick Start

```bash
# Install scraper dependencies
pip install -r scripts/requirements.txt

# Run changelog scraper manually
python scripts/scrape_changelogs.py

# Build and serve the dashboard
cd site
npm install
npm run dev
```

## Updating Feature Parity

Edit `data/features.yaml` to update feature status. Valid statuses:
- `ga` — Generally Available
- `preview` — In preview/beta
- `in_progress` — Being actively developed
- `planned` — Planned but not started
- `not_started` — No known plans
- `removed` — Previously available, removed
- `n_a` — Not applicable to this SDK
