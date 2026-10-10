# Release and recovery

Publishing requires explicit maintainer authorization. Prerelease/development
versions cannot pass the final tag check. Local gates never publish.

1. Review the complete diff and compatibility changes. Set one final version in
   `pyproject.toml` and `pdf2mp3/pdf2mp3.py`; add the same dated CHANGELOG heading.
   Review README, API/CLI references, support and provider/demo guides for stale
   development-version/status text. Describe the final package's commands and
   actual installation channel; keep known platform/provider limits explicit.
   Verify documentation links and examples for the release source/artifacts.
2. On the intended source, run `python scripts/quality.py release --base v1.0.0`.
   Inspect all reports and the support matrix CI. Confirm provider limitations
   and release notes. Required unresolved checks block release readiness.
3. After the release PR is merged into `main` and publication is authorized,
   create the matching `v<version>` tag on that integrated commit. The release
   workflow checks tag/version/changelog, verifies that the checkout matches the
   tag and is an ancestor of `origin/main`, and runs the release profile and OS/Python matrix,
   then downloads and verifies the tested wheel/sdist hashes and commit identity.
   The publish job does not rebuild the distributions.
4. Approve the waiting `pypi` environment deployment after reviewing the source,
   successful jobs and artifact evidence. Only `byraphaelmedeiros` is a required
   reviewer. Self-review is allowed because there is one maintainer; administrator
   bypass is disabled. Deployment policy accepts only tags matching `v*`.
   The publish job uses PyPI Trusted Publishing, with `id-token: write` scoped
   to that job, and uploads the tested artifacts without a permanent API token.
5. Verify the resulting PyPI metadata/files against the retained artifact hashes
   and install/help checks from a new environment. A passed upload alone is not
   runtime verification. Never claim publication without registry readback.
   Check the rendered README links and final-version installation/help examples
   as well; distinguish verified publication from earlier local preparation.

## Trusted Publishing configuration

Before using the OIDC workflow, the PyPI project owner must register and verify
this publisher in the project's Publishing settings:

| Field | Value |
| --- | --- |
| Provider | GitHub Actions |
| Owner | `byraphaelmedeiros` |
| Repository | `pdf2mp3` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

The registration is external configuration, not created by merging workflow
files. Confirm it on PyPI before integrating the OIDC migration. Keep the legacy
`PYPI_API_TOKEN` secret until the first explicitly authorized OIDC release has
been verified, then revoke the corresponding PyPI token and delete the GitHub
secret with maintainer authorization. The new workflow never reads that secret.
Do not publish a throwaway version to test the migration.

The maintainer controls release tags and publication. Contributors can propose
release changes through PRs, but cannot merge them, create repository tags or
approve the publishing environment. Keep PyPI project owners and publishers
limited to those intentionally authorized; GitHub permissions do not restrict
separate PyPI credentials or publisher registrations.

## Repository protections

`main` requires a PR, current-base quality checks, resolved review conversations
and linear history. The sole maintainer merges manually using squash; there is
no ruleset bypass. Approval count is zero while there is only one maintainer.
Tags matching `v*` cannot be updated or deleted. Immutable GitHub releases apply
to future published releases; they do not retroactively freeze older releases.
Prepare a draft release and attach all intended assets before publishing it.

Actions are restricted to the actions used for CI, publishing and CodeQL. Keep
action references pinned to full commit SHAs and review Dependabot updates.
The repository requires full commit SHA pins. The `ci-required` aggregate
requires the release quality gate and all nine compatibility jobs; it fails when
the reusable quality workflow fails, is cancelled or is skipped. Do not require
release-only jobs (`version` or `publish`) for ordinary PRs.

If a gate fails, retain its logs and resolve the cause; do not publish around it.
For a published regression, stop further rollout, document the affected versions,
prepare a corrective version and consider yanking the bad release through an
authorized maintainer. Do not overwrite an existing release or rewrite its tag.
Users can temporarily pin the last known compatible version, considering its
Python requirements and known security limitations. Do not recommend restoring
an old vulnerable PDF parser as a security fix.
