# GitHub security controls

Date: 2026-11-14

This record documents the approved credential-theft/CI-injection hardening. It is not evidence that an account was compromised. Changes preserve the existing application runtime.

## Verified server changes

- Actions: enabled → disabled. No workflows are present; disabling execution prevents newly injected workflows from running. Verified with GET actions/permissions.
- Default branch: unprotected → PR required, administrator enforcement, linear history, conversation resolution, force-push/deletion blocked. Zero required approvals preserves the single-owner workflow; this provides traceability, not independent review. Verified with GET branch protection.

## Workflow changes and verification

No workflows, dependencies or application code were added. Validation consists of API read-back and documentation checks.

## Limits and rollback

Write credentials, administrator access and production integrations still require independent review. Re-enable Actions only after reviewing every branch and documenting a need for CI. Restore previous controls only through an approved change; revert code through a PR, never a history rewrite.

[Central policy and audit record](https://github.com/notolac/home-lab/blob/main/_shared/orquestacion/github-hardening.md).
