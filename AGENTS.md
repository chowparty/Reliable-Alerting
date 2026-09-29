# Team working rules

These rules apply throughout this repository.

## Working style

- Use relevant available skills and workflows: brainstorm before design or behaviour changes, investigate failures systematically, and verify before claiming completion.
- Read relevant files before editing. Make the smallest correct change and preserve unrelated work.
- Keep explanations clear and beginner-friendly; briefly explain consequential choices without narrating every action.
- Keep agent-management details out of project documentation. Avoid unnecessary dependencies, abstractions, documents, and scaffolding.

## Boundaries

- Stay within the repository unless explicitly authorized otherwise. Do not read secrets, credentials, `.env` files, private notes/data, or external symlink targets without authorization.
- Ask before destructive actions, large refactors, new dependencies, breaking changes, auth/billing work, or external publication.
- Do not edit generated files manually or commit secrets, raw datasets, large generated results, checkpoints, caches, or machine-specific environments.
- Distinguish small intentional test fixtures from datasets and generated artifacts. Review file contents before staging; ignore rules are not a substitute for review.

## Scientific integrity

- Keep loading, chronological splitting, preprocessing/scoring, calibration, decision policies, and evaluation separate. Build reusable research components; synthetic checks must exercise those same components.
- Fit preprocessing only on permitted source data and explicitly declare source-label use. Preserve chronology and split boundaries; use only information available at decision time.
- Keep evaluation labels out of runtime scoring and policy decisions. Save predictions before joining evaluation labels.
- Reserve held-out evaluation data before outcome inspection and freeze choices before evaluating it. Do not select streams because their results look favourable or retune on held-out outcomes.
- Record enough configuration, data provenance, environment information, and result traces to reproduce reported findings.
- Compare policies on the same scores. Separate ranking metrics from policy metrics: identical score traces cannot demonstrate a policy improvement through VUS-PR.
- Form alert episodes from predictions before consulting labels. Respect actual decision availability at window end; do not backdate alerts.
- Report alert volume, decision coverage, and resource use as different quantities.
- Distinguish measured results, assumptions, hypotheses, and unresolved questions. Deferral, diagnostics, and recalibration are candidate ideas; a defer streak alone neither identifies an anomaly nor justifies recalibration. Negative, null, and inconclusive findings are valid, but do not automatically establish a publishable contribution.

## Evidence and citations

Primary academic evidence and citations must come from these platforms:

- [IEEE Xplore](https://ieeexplore.ieee.org/)
- [ACM Digital Library](https://dl.acm.org/)
- [SpringerLink](https://link.springer.com/)
- [ScienceDirect / Elsevier](https://www.sciencedirect.com/)
- [NeurIPS Proceedings](https://proceedings.neurips.cc/)
- [PMLR](https://proceedings.mlr.press/), including ICML and AISTATS
- [ACL Anthology](https://aclanthology.org/)

Other sources are discovery/background only. Unverified information is not evidence that prior work lacks a feature. Use official documentation for software-specific claims. Never invent citations, APIs, paths, or verification results.

## Verification

- Use meaningful tests for implemented features and fixes; prefer standard-library `unittest` until another test dependency is agreed.
- For the initial scaffold, verify actual setup, imports, and configuration as applicable. Avoid tests that merely assert empty directories exist.
- Never claim an unrun check passed. Report blockers and failed checks honestly.

## Git conventions and approval

- Use Conventional Commits: `type(optional-scope): concise summary`.
- Include a meaningful commit body describing what changed, why, and relevant verification or limitations.
- Do not include AI attribution, AI references, or `Co-Author` / `Co-authored-by` trailers in commit messages.
- Do not change Git identity/configuration without approval. Do not bypass hooks, force-push, amend published history, or commit unrelated files.
- Stage only intended, reviewed files using explicit paths. Before committing and pushing, review the staged changes, verification, full commit message, and intended branch/remote/push command.

### Standing authorization for the Phase-I report cycle (2026-09-29)

The following hard constraints must be followed:

- No AI attribution, AI references, or `Co-Author` / `Co-authored-by` trailers
  anywhere in commit messages (this restates the rule above; it is not relaxed).
- Every commit uses a Conventional Commit subject plus a body written in plain,
  beginner-friendly language describing what changed and why.
- Push only source code and files that genuinely belong in the repository. Do
  NOT commit planning or scaffolding artifacts — `report-planning/`,
  `report-work/`, intake notes, drafts, or any file living outside `research/`.
  Continue to exclude datasets, large generated results, checkpoints, and caches.
- All other durable rules above still apply: explicit-path staging, review of
  file contents before staging, no force-push, no history rewrite, no Git
  identity change, no hook bypass, no committing unrelated files.
