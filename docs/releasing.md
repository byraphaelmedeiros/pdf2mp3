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
3. After authorization, create the matching `v<version>` tag. The release workflow
   checks tag/version/changelog, runs the same release profile and OS/Python matrix,
   then downloads and verifies the tested wheel/sdist hashes and commit identity.
   The publish job does not rebuild the distributions.
4. The existing `pypi` environment and `PYPI_API_TOKEN` secret remain required.
   Repository maintainers should protect that environment and require the quality
   jobs for merge. These settings are remote configuration, not changed by this
   local work. A future trusted-publishing migration needs separate configuration.
5. Verify the resulting PyPI metadata/files against the retained artifact hashes
   and install/help checks from a new environment. A passed upload alone is not
   runtime verification. Never claim publication without registry readback.
   Check the rendered README links and final-version installation/help examples
   as well; distinguish verified publication from earlier local preparation.

If a gate fails, retain its logs and resolve the cause; do not publish around it.
For a published regression, stop further rollout, document the affected versions,
prepare a corrective version and consider yanking the bad release through an
authorized maintainer. Do not overwrite an existing release or rewrite its tag.
Users can temporarily pin the last known compatible version, considering its
Python requirements and known security limitations. Do not recommend restoring
an old vulnerable PDF parser as a security fix.
