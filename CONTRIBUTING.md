# Contributing

This repo is **private and internal** to the Azure Cosmos DB SDK team. It is
the parity dashboard used by SDK leads (.NET, Java, Python, Go, Rust) and
anyone tracking cross-SDK feature / retry / failover behavior.

If you are an SDK lead, **you are the authoritative reviewer for your SDK's
rows**. Nobody else should merge changes to your SDK columns without your
sign-off.

---

## Who this is for

- **SDK leads** (.NET, Java, Python, Go, Rust): keep your SDK's entries
  accurate; review PRs that touch your columns.
- **PMs, architects, support engineers**: propose edits via PR when you find
  an inaccuracy or a new feature to track.
- **Anyone tracking parity**: read-only via the dashboard; file PRs for fixes.

---

## Source-of-truth files

All curated data lives under `data/` and is hand-maintained. Do not generate
these files from scripts.

| File                   | Purpose                                                                                       |
|------------------------|-----------------------------------------------------------------------------------------------|
| `data/features.yaml`   | Feature × SDK parity matrix (CRUD, batch, CFP, query, etc.). Grouped by category.             |
| `data/retries.yaml`    | Retry-behavior × SDK × connection-mode matrix. Each cell pinned by `source_ref`.              |
| `data/failovers.yaml`  | Multi-region / failover × SDK matrix. Each cell pinned by `source_ref` where possible.        |
| `data/sdks.yaml`       | SDK metadata: package names, repo URLs, changelog paths, current versions.                    |

Scraper output lives under `data/scraped/` and is **machine-written**. Do not
edit those files by hand — they are rewritten on every cron run.

---

## Editing a feature row

Open `data/features.yaml`. The schema is documented in the comments at the
top of the file — read those first; they are the canonical reference.

Quick summary:

- **`status`** (required) — one of:
  `ga`, `preview`, `in_progress`, `planned`, `not_started`, `removed`, `n_a`.
- **`since`** — SDK version the feature shipped in. Required for `ga`,
  `preview`, and `removed`. Omit for `not_started` / `planned`.
- **`pr_url`** — upstream PR link. Required for `in_progress`; strongly
  encouraged for recent `ga` / `preview` / `removed` entries so reviewers can
  verify.
- **`notes`** — short free-form context (e.g. "Removed for API redesign",
  "Gateway-mode only"). Keep to one line where possible.

Bump the `# Last updated:` comment at the top of `features.yaml` when you
land a change.

> **Assessment hints (coming soon):** a richer per-SDK `assessment` block
> (detection hints, symbol names, doc links) is being designed on branch
> [`ft/feature-assessment-hints`](../../tree/ft/feature-assessment-hints).
> That branch may not be merged yet — always check the current schema in
> `data/features.yaml` before adding new fields. Once merged, it will be the
> recommended way to contribute SDK-specific detection knowledge.

---

## Editing retries / failovers

See the schema in `README.md` and the comments at the top of `data/retries.yaml`
and `data/failovers.yaml`. Every cell **must** include a `source_ref` pinning
the claim to a specific file and line in the upstream SDK repo. If you can't
verify from source, use `status: unknown` with a short `notes` — never guess.

---

## Weekly cron vs. manual edits

The weekly workflow (`.github/workflows/update-parity.yml`) runs every Monday
and:

1. Scrapes SDK changelogs into `data/scraped/`.
2. Hashes watched source files listed under each YAML's `audit_refs:` and
   writes drift reports to `data/scraped/*_drift.md`.
3. Builds a snapshot JSON for the site.

**Invariant:** the cron never overwrites `data/features.yaml`,
`data/retries.yaml`, `data/failovers.yaml`, or `data/sdks.yaml`. It only
writes into `data/scraped/`. When drift is reported, a **human** must
re-audit the affected source file and update the curated YAML by hand, then
bump `last_audited:` (retries/failovers) or `# Last updated:` (features).

---

## Per-SDK ownership

<!-- TODO(repo owner): fill in GitHub handles for each SDK lead. -->

| SDK    | Lead (GitHub handle) |
|--------|----------------------|
| .NET   | `@dotnet-lead-tbd`   |
| Java   | `@java-lead-tbd`     |
| Python | `@python-lead-tbd`   |
| Go     | `@go-lead-tbd`       |
| Rust   | `@rust-lead-tbd`     |

Changes that touch an SDK's rows require that SDK's lead to approve, even
though `CODEOWNERS` can't path-match inside a YAML file (see
`.github/CODEOWNERS`). Tag the lead on the PR.

---

## PR workflow

1. **Branch name:** `ft/<sdk>-<feature>` — e.g. `ft/rust-bulk-operations`,
   `ft/java-circuit-breaker`. For cross-SDK changes, use
   `ft/<area>-<short-desc>` (e.g. `ft/retries-429-rewording`).
2. **One logical change per PR.** Don't mix a Rust refresh with a Java
   refresh — split them. Reviewers and `git blame` both benefit.
3. **Cite sources in the PR description.** For every changed cell, include:
   - The upstream SDK repo + commit SHA or PR link.
   - The CHANGELOG entry (quote the line) when relevant.
   - For retries/failovers: the file + line number your `source_ref` points
     at.
4. **Bump `Last updated` / `last_audited`** in the affected YAML.
5. **Fill out the PR template** (`.github/PULL_REQUEST_TEMPLATE.md`).
6. **Verify locally:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('data/features.yaml'))"
   cd site && npm install && npm run build
   ```
7. **Tag the SDK lead(s)** whose columns you touched.

---

## Requesting a full re-audit of a category

If you think an entire category (e.g. "Change Feed", or all retry scenarios
for Python) is stale, **open an issue** titled
`re-audit: <category> (<sdk or "all">)` with:

- What makes you think it's stale (release, behavior change, customer ticket).
- Which upstream commits / PRs should be checked.
- Any customer impact or urgency.

The SDK lead for that column will pick it up, or delegate. Do not silently
flip statuses to `unknown` across a whole category without an issue — that
makes the diff hard to review.

---

## Questions

Ping the Cosmos DB SDK team channel, or open an issue.
