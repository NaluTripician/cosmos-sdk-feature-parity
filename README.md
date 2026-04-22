# Cosmos DB SDK Feature Parity Dashboard

A private dashboard tracking feature parity — and retry behavior — across all Azure Cosmos DB NoSQL SDKs.

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
2. **`data/retries.yaml`** — Curated retry-behavior × SDK × connection-mode matrix (source of truth)
3. **`data/sdks.yaml`** — SDK metadata (repos, changelog paths, versions)
4. **`scripts/`** — Python scripts to scrape changelogs, detect retry-policy drift, and build snapshots
5. **`site/`** — Static React dashboard (deployed to GitHub Pages) with **Features** and **Retries** tabs
6. **`.github/workflows/`** — Weekly cron to update data and redeploy

## Quick Start

```bash
# Install scraper dependencies
pip install -r scripts/requirements.txt

# Run changelog scraper manually
python scripts/scrape_changelogs.py

# Detect drift in retry-policy source files
python scripts/scrape_retry_policies.py

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

## Updating Retry Behavior

`data/retries.yaml` describes, for each retry *scenario* (HTTP status + optional Cosmos sub-status)
and each supported connection mode, how every SDK handles the error. Every cell must include a
`source_ref` pinning the claim to a specific file and line in the SDK repo — this is how accuracy
is enforced.

### Schema

```yaml
sdks:
  dotnet: { connection_modes: [direct, gateway], default_mode: direct }
  # ...

audit_refs:                             # files the drift detector watches
  dotnet:
    - Microsoft.Azure.Cosmos/src/ResourceThrottleRetryPolicy.cs
    # ...

categories:
  - name: "HTTP status retries"
    scenarios:
      - id: throttled_429
        name: "Throttled (429)"
        status_code: 429
        sdks:
          dotnet:
            direct: { status: retries, max_retries: 9, wait_strategy: "server_retry_after", ... }
            gateway: { ... }
          # SDKs with a single mode can either nest under `gateway:` or omit the mode key.
```

Valid per-cell fields: `status` (`retries` | `no_retry` | `n_a` | `not_started` | `unknown`),
`max_retries`, `wait_strategy`, `total_wait_cap_s`, `cross_region`, `direct_only`, `source_ref`,
`notes`.

### Drift detection

`scripts/scrape_retry_policies.py` fetches every file in `audit_refs`, hashes the normalized
content with SHA-256, and compares to the last run (stored in
`data/scraped/retry_policies_latest.json`). When any file's hash changes, the SDK is flagged
`drift_detected: true` and a `data/scraped/retry_drift.md` report is written. The scraper
**never** mutates `retries.yaml` — a human must re-audit the affected file and update curated
behavior.

### When drift is reported

1. Read `data/scraped/retry_drift.md` for the flagged files + commit links.
2. Diff the new commit against the previous hash and identify behavioral changes.
3. Update the affected cells in `data/retries.yaml`, refreshing `source_ref` line numbers.
4. Bump `last_audited:` at the top of `retries.yaml`.
5. Commit both files; the next scraper run will clear the drift report.

## Weekly Workflow

`.github/workflows/update-parity.yml` runs every Monday at 06:00 UTC:

1. Scrape SDK changelogs (`scrape_changelogs.py`)
2. Scrape retry-policy source files, detect drift (`scrape_retry_policies.py`)
3. Generate parity snapshot (`generate_snapshot.py`)
4. Commit changed `data/` files
5. Build and deploy the site

