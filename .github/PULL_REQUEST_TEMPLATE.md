<!--
Thanks for contributing to the Cosmos DB SDK parity dashboard!
Please fill in each section. See CONTRIBUTING.md for the full workflow.
-->

## Summary

<!-- One or two sentences: what is changing and why. -->

## Affected SDKs

<!-- Check all that apply. Tag the SDK lead(s) in the PR as reviewers. -->

- [ ] .NET
- [ ] Java
- [ ] Python
- [ ] Go
- [ ] Rust
- [ ] Cross-SDK / schema / tooling only

## Source citations

<!--
For every changed cell, link to the upstream evidence:
  - SDK repo + commit SHA or PR link
  - Quoted CHANGELOG line, if applicable
  - For retries/failovers: file + line backing the `source_ref`
-->

-

## Verification

- [ ] `python -c "import yaml; yaml.safe_load(open('data/features.yaml'))"` (and retries/failovers if touched) passes
- [ ] `cd site && npm install && npm run build` succeeds
- [ ] Ran the dashboard locally (`npm run dev`) and confirmed the affected rows render correctly

## Checklist

- [ ] Bumped the `# Last updated:` comment in the affected YAML (or `last_audited:` for retries/failovers)
- [ ] Added / updated the assessment block if relevant (see `ft/feature-assessment-hints` if merged; otherwise current schema in `data/features.yaml`)
- [ ] One logical change per PR (no unrelated SDK refreshes bundled in)
- [ ] Branch name follows `ft/<sdk>-<feature>` (see CONTRIBUTING.md)
- [ ] Tagged the owning SDK lead(s) as reviewers
