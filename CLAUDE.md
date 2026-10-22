## Current GitHub and CI/CD instructions (2026-10-22)

- Canonical source is `https://github.com/HallyAus/OVO_Aus_api`. Push completed, validated work and releases to GitHub only, on the current correct branch; verify `git remote -v` and preserve local work. GitHub is not a backup mirror.
- A self-hosted GitHub Actions runner is available. Use it for workflows configured in the repository after checking actual labels, permissions and operating environment. Never assume an Action ran or that a push deployed production.
- Keep existing security controls, project tests, protected acceptance, same-artifact promotion, scheduled jobs, service secrets and rollback checks. Do not enable/alter deployment triggers without validating the configured route.
- These source-control instructions override outdated historical remotes, mirrors and disabled-Actions notes elsewhere in this document.

@AGENTS.md
