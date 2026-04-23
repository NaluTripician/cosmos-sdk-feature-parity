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
5. **`scripts/`** — Python scripts to scrape changelogs, scrape SDK PRs, scrape public API surfaces (Rust docs.rs + all-SDK), detect source-file drift, and build snapshots
6. **`site/`** — Static React dashboard (deployed to GitHub Pages) with **Features**, **Retries**, **Failovers**, **Recent Activity**, and **GA Readiness** tabs. The **GA Readiness** tab lets any SDK lead pick a target SDK (defaults to Rust) and see the feature gaps where their SDK is behind while ≥2 other SDKs are already GA — i.e., the likely GA blockers. Share the view with `?tab=ga-readiness&sdk=<sdk>`.
7. **`.github/workflows/`** — Weekly cron (`update-parity.yml`) to refresh scraped data, plus `deploy-site.yml` which rebuilds and redeploys the site on every push to `main` that touches `data/**`, `site/**`, or the copy/validate scripts. Manually triggerable via **Run workflow** in the Actions tab.

## Quick Start

```bash
# Install scraper dependencies
pip install -r scripts/requirements.txt

# Run changelog scraper manually
python scripts/scrape_changelogs.py

# Fetch recent PRs per SDK (last 14 days) -> data/scraped/recent_prs_latest.json
python scripts/fetch_recent_prs.py

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

### Per-cell tier + issue links

Each per-SDK cell may additionally carry two classification / tracking fields:

- `tier` — one of `ga_blocker`, `post_ga`, `nice_to_have`. Classifies the
  feature's priority for **that specific SDK**. The GA Readiness view uses
  this to split "real" GA blockers from features intentionally deferred
  past GA (e.g. Rust Change Feed Processor is tagged `tier: post_ga`).
- `issues` — a non-empty list of tracking-issue objects, each
  `{ url: <gh-issue-url>, title?: <string>, labels?: [<string>, ...] }`.
  Rendered as 🐛 chips in the matrix. The URL must be `http://` or
  `https://`; beyond that no format check is enforced (GitHub issues, ADO
  work items, internal trackers all work). The optional `labels` list is
  consumed by the tier → label write-back workflow and propagated to the
  linked GitHub issue; label strings must be non-empty.

Label names for the three tiers can be configured at the root of
`features.yaml`:

```yaml
tier_label_map:
  ga_blocker: parity/ga-blocker
  post_ga: parity/post-ga
  nice_to_have: parity/nice-to-have
```

Omitting the map falls back to the defaults shown above.

### Editing tiers from the site (no PR required up front)

The parity site has an **"✏️ Edit tiers"** toggle next to the filter buttons.
Turning it on replaces each cell's tier badge with a dropdown. Staged
changes are tracked locally (nothing is submitted yet) and a floating panel
summarises them.

Clicking **⬇️ Download patch (JSON)** saves a file like:

```json
{
  "generated_at": "2026-04-23T15:00:00.000Z",
  "generated_by": "parity-site/tier-editor",
  "changes": [
    {"feature_id": "binary_encoding", "sdk_id": "java", "tier": "nice_to_have"},
    {"feature_id": "change_feed_processor", "sdk_id": "rust", "tier": null}
  ]
}
```

Apply it locally to `data/features.yaml`, then commit + PR as usual:

```powershell
python scripts/apply_tier_patch.py tier-patch-*.json
python scripts/validate_features_schema.py   # sanity check
cd site; npm run build                        # sanity check
git add data/features.yaml; git commit ...
```

The script edits the YAML **line-by-line** so comments, flow-style
spacing, and quoting are preserved byte-for-byte outside the touched
cells. Both single-line (`dotnet: { status: "ga" }`) and multi-line
block cells are supported. `--dry-run` previews without writing.

No PAT, no browser auth — the site only ever produces a downloadable
patch, never contacts GitHub directly.

Example:

```yaml
rust:
  status: "not_started"
  tier: "post_ga"
  issues:
    - url: https://github.com/Azure/azure-sdk-for-rust/issues/1234
      title: "Track Change Feed Processor post-GA"
      labels:
        - parity/rust-post-ga
```

## Assessment Hints

Each feature in `data/features.yaml` may carry an **optional** `assessment:`
block that embeds SDK-specific detection knowledge — the stuff you would
otherwise have to put in a Copilot prompt every time you re-audit the matrix.

This is the **recommended way for SDK leads** (e.g. Ashley on Rust, the .NET
FaultInjection owners, etc.) to contribute detection knowledge for their SDK
via a PR **that only touches the `assessment:` block of the features they
own** — without editing parity cells for other SDKs. Per-SDK assessment PRs
are intended to be fast, low-conflict, and incremental; the block is
additive and orthogonal to the `sdks:` cells.

### Schema

```yaml
- id: fault_injection
  name: "Fault Injection"
  description: "Simulate failures for resilience testing"
  assessment:                              # OPTIONAL
    notes_for_reviewer: |
      Free-form text aimed at the human (or agent) re-auditing this
      feature. Call out non-obvious shipping vehicles — separate NuGet
      packages, Cargo feature flags, preview build tags, etc.
    public_api_symbols:                    # per SDK, list of strings
      dotnet: ["Microsoft.Azure.Cosmos.FaultInjection.FaultInjectionRule"]
      java:   ["com.azure.cosmos.test.faultinjection.FaultInjectionRule"]
      python: ["azure.cosmos.faults.FaultInjectionTransport"]
      rust:   ["azure_data_cosmos::fault_injection"]
    detection_hints:                       # per SDK, list of strings
      rust:   ["fault_injection"]
      dotnet: ["separate_package:Microsoft.Azure.Cosmos.FaultInjection"]
    changelog_keywords:                    # flat list of strings
      - "fault injection"
      - "FaultInjection"
  sdks:
    # ... parity cells unchanged ...
```

All four sub-keys (`notes_for_reviewer`, `public_api_symbols`,
`detection_hints`, `changelog_keywords`) are optional. Valid SDK ids are
`dotnet`, `java`, `python`, `go`, `rust`.

> Note: `detection_hints` is intentionally *not* reused as a runtime-opt-in
> marker. Entries here are purely detection hints for scrapers (e.g.
> "grep the Cargo.toml for this string") — they do not assert anything
> about runtime behavior. Keep any future per-cell runtime-opt-in field
> (e.g. `requires_opt_in`) distinct from this block.

If a sub-key is present, its list must be non-empty; the validator
rejects empty lists (omit the key instead).

#### Item grammar for `public_api_symbols` and `detection_hints`

Each string inside these per-SDK lists is interpreted by the scraper as
follows:

- **Plain string** (e.g. `"azure_data_cosmos::fault_injection"`) — matched
  verbatim against symbols / flags / build tags inside the SDK's default
  package (the package listed in `data/sdks.yaml` for that SDK).
- **`separate_package:<crate-or-package-name>`** — instructs the scraper
  to look inside a *different* package instead of the SDK's default
  package. Use this when a feature ships in a sibling NuGet package,
  companion crate, or test-only artifact.

Example — Fault Injection ships in a separate NuGet on .NET and behind a
Cargo feature on Rust:

```yaml
detection_hints:
  rust:   ["fault_injection"]                                         # plain Cargo feature
  dotnet: ["separate_package:Microsoft.Azure.Cosmos.FaultInjection"]  # look in this NuGet, not the main SDK package
```

### How the scripts consume it

- **`scripts/scrape_changelogs.py`** — when matching changelog bullet
  points to feature ids, now ANDs in a substring match against each
  feature's `assessment.changelog_keywords` on top of the legacy
  built-in `FEATURE_PATTERNS` regex table. Features without an
  `assessment` block fall back to the legacy regex behavior, so this
  change is fully backward compatible.
- **`scripts/generate_snapshot.py`** — re-runs the same
  assessment-keyword match over the scraped data and records the hits
  under `assessment_keyword_hits` in the daily snapshot, as a stronger,
  owner-curated signal alongside the existing `recent_features_detected`.
- **`scripts/validate_features_schema.py`** — validates the optional
  `assessment:` block's shape. Run it (or let the weekly workflow run it)
  before any scraping.

### Submitting an assessment PR

SDK owners who want to refine detection for their SDK should open a PR
that:

1. Touches **only** the `assessment:` blocks of the features they own.
2. Does **not** change `sdks:` parity cells (those are owned by whoever
   audits the matrix as a whole).
3. Passes `python scripts/validate_features_schema.py`.

This keeps parity-review PRs and assessment-hint PRs orthogonal and easy
to merge.


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

1. Validate `data/features.yaml` schema incl. optional `assessment:` blocks (`validate_features_schema.py`)
2. Scrape SDK changelogs (`scrape_changelogs.py`)
3. Scrape retry-policy source files, detect drift (`scrape_source_refs.py --data data/retries.yaml`)
4. Scrape failover source files, detect drift (`scrape_source_refs.py --data data/failovers.yaml`)
5. Scrape the Rust `azure_data_cosmos` public API + Cargo features from docs.rs, detect drift (`scrape_public_api_rust.py`). The Rust CHANGELOG misses features, so the public API surface is used as an additional signal when auditing `data/features.yaml`. Never auto-mutates curated YAML.
6. Scrape public API surfaces across all SDKs (`scrape_public_api.py`, `continue-on-error`)
7. Generate parity snapshot (`generate_snapshot.py`)
8. Commit changed `data/` files
9. Build and deploy the site

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

