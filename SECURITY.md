# Security Policy

## Supported Versions
Only the latest released version of **pdf2mp3** is supported with security updates.

## Reporting a Vulnerability
If you discover a security vulnerability:
- Do **not** open a public issue.
- Use [GitHub private vulnerability reporting](https://github.com/byraphaelmedeiros/pdf2mp3/security/advisories/new).
- Alternatively, email the maintainer directly: pdf2mp3@byraphaelmedeiros.com.
- Expect a response within 72 hours.

## Known development dependency finding

As of 2026-10-08, the 2.0.0 optional gTTS installation resolves to
**gTTS 2.5.4**, whose `click>=7.1,<8.2` requirement selects **Click 8.1.8**.
Earlier audits reported **PYSEC-2026-2132 / CVE-2026-7246** for `click.edit()`.
The [OSV record](https://osv.dev/vulnerability/PYSEC-2026-2132) was withdrawn on
**2026-10-07**. The
[canonical CVE record](https://github.com/CVEProject/cvelistV5/blob/main/cves/2026/7xxx/CVE-2026-7246.json)
is still published but marked disputed: its description says Pallets does not
consider it a valid vulnerability and that assignment did not follow CVE rules.
The original advisory and Click 8.3.3 hardening remain documented upstream.
Current resolved-environment audits report no finding for Click 8.1.8; this is
an upstream advisory change, not a dependency upgrade or a local exemption.

PDF2MP3 uses argparse and does not call `click.edit()`. That reachability
observation and the withdrawn advisory do not certify an environment as free of
all vulnerabilities. Keep this dependency constraint and historical finding
visible for security review before a release.

Sources: [gTTS 2.5.4](https://pypi.org/project/gTTS/2.5.4/), installed dependency
metadata, [PyPA advisory](https://github.com/pypa/advisory-database/blob/main/vulns/click/PYSEC-2026-2132.yaml)
and [Click changes](https://click.palletsprojects.com/en/stable/changes/#version-8-3-3).

The base package does not require gTTS or Click. Base and extra audits are
reported separately. The historical finding no longer makes the current
automated gate fail; any active finding still fails it. No security exception has
been granted, and no release is authorized by a passing audit.
Do not force an incompatible Click override, bypass dependency resolution or
relax the audit. Any future dependency or provider change requires compatibility
and security validation before qualifying a release.
