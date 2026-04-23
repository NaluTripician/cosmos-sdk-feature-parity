# Cosmos DB SDK Feature Parity Dashboard

A private dashboard tracking feature parity — and retry behavior — across all Azure Cosmos DB NoSQL SDKs.

> 📣 **Contributing?** SDK leads and anyone proposing edits should read
> [**CONTRIBUTING.md**](./CONTRIBUTING.md) first — it covers source-of-truth
> files, the weekly-cron invariants, branch naming, PR expectations, and
> per-SDK ownership.

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
3. **`data/failovers.yaml`** — Curated multi-region / failover × SDK matrix (source of truth)
4. **`data/sdks.yaml`** — SDK metadata (repos, changelog paths, versions)
5. **`scripts/`** — Python scripts to scrape changelogs, scrape the Rust public API from docs.rs, detect source-file drift, and build snapshots
6. **`site/`** — Static React dashboard (deployed to GitHub Pages) with **Features**, **Retries**, and **Failovers** tabs
7. **`.github/workflows/`** — Weekly cron to update data and redeploy

## Quick Start

```bash
# Install scraper dependencies
pip install -r scripts/requirements.txt

# Run changelog scraper manually
python scripts/scrape_changelogs.py

# Detect drift in retry-policy source files
python scripts/scrape_source_refs.py --data data/retries.yaml --output retry_policies --label retry-policy

# Detect drift in failover source files
python scripts/scrape_source_refs.py --data data/failovers.yaml --output failover_policies --label failover-policy

# Scrape public API surfaces across all SDKs (signal-only)
python scripts/scrape_public_api.py            # all SDKs
python scripts/scrape_public_api.py --sdk go   # single SDK

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

### Orthogonal per-cell availability fields

The flat `status` enum can't capture every availability nuance (e.g. a feature that
is shipped but gated behind a Cargo feature flag, a separate NuGet package, a
system property, or an internal-only transport). Each per-SDK cell may optionally
include the following orthogonal fields alongside `status`:

- `requires_opt_in` — how a user must opt in. One of:
  - `cargo_feature` — Rust Cargo feature flag (e.g. `fault_injection`)
  - `system_property` — Java/JVM system property (e.g. `azure.cosmos.thinClientEnabled`)
  - `separate_package` — shipped as a separate package (e.g. `Microsoft.Azure.Cosmos.FaultInjection`)
  - `env_var` — environment variable
  - `preview_flag` — preview/client-option flag (e.g. `CosmosClientOptions.EnablePartitionLevelCircuitBreaker`)
- `opt_in_name` — the concrete flag / property / package / option name.
- `public_api` — boolean. Defaults to `true` when absent. Set to `false` for
  internal-only surfaces that aren't part of the public API, even when
  `status` is `ga` or `preview` (e.g. Python `FaultInjectionTransport`).

These fields are back-compatible: omitting them preserves current behavior. The
dashboard renders a small badge (⚑ for opt-in, 🔒 for internal-only) next to the
status pill, with a tooltip showing the opt-in name.

Example:

```yaml
dotnet: { status: "ga", requires_opt_in: "separate_package", opt_in_name: "Microsoft.Azure.Cosmos.FaultInjection" }
java:   { status: "preview", requires_opt_in: "system_property", opt_in_name: "azure.cosmos.thinClientEnabled", public_api: false }
python: { status: "preview", public_api: false, notes: "test utility only" }
```

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

`scripts/scrape_source_refs.py` is a generic scraper: point it at any curated
YAML (retries or failovers) with an `audit_refs` section and it fetches every
listed file, hashes the normalized content with SHA-256, and compares to the
last run (stored in `data/scraped/<output>_latest.json`). When any file's hash
changes, the SDK is flagged `drift_detected: true` and a
`data/scraped/<output>_drift.md` report is written. The scraper **never**
mutates the curated YAML — a human must re-audit the affected file and update
behavior.

`scripts/scrape_retry_policies.py` is kept as a backward-compatible shim that
calls the generic scraper with retry-specific arguments.

### When drift is reported

1. Read `data/scraped/retry_drift.md` for the flagged files + commit links.
2. Diff the new commit against the previous hash and identify behavioral changes.
3. Update the affected cells in `data/retries.yaml`, refreshing `source_ref` line numbers.
4. Bump `last_audited:` at the top of `retries.yaml`.
5. Commit both files; the next scraper run will clear the drift report.

## Weekly Workflow

`.github/workflows/update-parity.yml` runs every Monday at 06:00 UTC:

1. Scrape SDK changelogs (`scrape_changelogs.py`)
2. Scrape retry-policy source files, detect drift (`scrape_source_refs.py --data data/retries.yaml`)
3. Scrape failover source files, detect drift (`scrape_source_refs.py --data data/failovers.yaml`)
4. Scrape the Rust `azure_data_cosmos` public API + Cargo features from docs.rs, detect drift (`scrape_public_api_rust.py`). The Rust CHANGELOG misses features, so the public API surface is used as an additional signal when auditing `data/features.yaml`. Never auto-mutates curated YAML.
5. Scrape public API surfaces across all SDKs (`scrape_public_api.py`, `continue-on-error`)
6. Generate parity snapshot (`generate_snapshot.py`)
7. Commit changed `data/` files
8. Build and deploy the site

## Public API surface scraper

CHANGELOGs miss features in every SDK (e.g. new public types can ship without
a changelog entry), so `scripts/scrape_public_api.py` captures the raw public
API surface for each SDK and writes structured artifacts to
`data/scraped/`:

| Artifact | Purpose |
|----------|---------|
| `<sdk>_public_api_latest.json` | Most recent snapshot — `{scraped_at, sdk, source_url, version, public_items: [{kind, path}]}` |
| `<sdk>_public_api_<YYYY-MM-DD>.json` | Dated historical snapshot |
| `<sdk>_public_api_drift.md` | Written only when `public_items` changed between runs (added/removed symbols) |

Sources per SDK:

- **.NET** — `learn.microsoft.com/en-us/dotnet/api/microsoft.azure.cosmos` overview
- **Java** — Azure SDK javadocs (`azuresdkdocs.z19.web.core.windows.net/java/azure-cosmos/latest/`)
- **Python** — Azure SDK Sphinx docs `genindex.html` + PyPI JSON for version
- **Go** — `pkg.go.dev/github.com/Azure/azure-sdk-for-go/sdk/data/azcosmos`
- **Rust** — stub on this branch; full docs.rs scraper lives on the sibling
  branch `ft/scrape-docs-rs`

Adapters live in `scripts/public_api_adapters/<sdk>.py`. Each returns a
uniform payload so downstream consumers (drift diffs, dashboards) don't need
per-SDK logic. Network failures are caught and written as a valid JSON stub
with an `error` field — the workflow step uses `continue-on-error: true` so
an outage in one doc site doesn't fail the weekly run.

**This scraper is signal-only — `data/features.yaml`, `data/retries.yaml`,
and `data/failovers.yaml` are NEVER auto-mutated.** Humans review drift
reports alongside `CHANGELOG.md` when deciding what to edit.

## Updating Failover Behavior

`data/failovers.yaml` describes, for each multi-region / failover *scenario*
(endpoint discovery, write/read endpoint resolution, PPAF, circuit breaker,
hedging, region exclusion, global-endpoint-manager internals), how every SDK
behaves. Each cell should include a `source_ref` pinning the claim to a
specific file + line in the SDK repo.

Status vocabulary is slightly different from retries:
`supported | partial | not_supported | not_started | n_a | unknown`.

When a cell can't be verified from source, leave it as `unknown` with a short
`notes` explanation — **never guess**.

