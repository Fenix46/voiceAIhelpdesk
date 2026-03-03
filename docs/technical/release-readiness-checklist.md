# Release Readiness Checklist

This checklist tracks production readiness for VoiceHelpDeskAI.

## P0 - Blocking (must be green before go-live)

- [x] `pyproject.toml` is syntactically valid and parseable.
- [x] Backend source compiles without Python syntax errors (`python -m compileall src`).
- [x] Frontend production bundle builds successfully (`npm run build` in `frontend/`).
- [ ] Backend app startup smoke test passes in a clean environment with all runtime dependencies installed.
- [ ] Core API endpoints used by the product are not placeholder implementations.
- [ ] End-to-end smoke test (frontend -> API -> Redis/DB) passes in deployment-like setup.

## P1 - High Priority (stability and operations)

- [ ] Lock runtime toolchains for reproducibility (`.python-version`, Node LTS, lockfile consistency).
- [ ] Ensure dependency strategy is consistent (`poetry` vs `requirements`); remove drift.
- [ ] Run unit/integration test suites in CI and enforce pass on main branch.
- [ ] Run security checks (`bandit`, dependency audit) and fix high severity findings.
- [ ] Validate migrations against target production DB (PostgreSQL).
- [ ] Verify background workers (`celery worker/beat`) in staging with real broker/backend.
- [ ] Replace hardcoded local URLs with environment-driven settings.

## P2 - Recommended (quality and maintainability)

- [ ] Remove stale TODO/placeholder code paths that are outside MVP scope.
- [ ] Add API contract tests for key endpoints.
- [ ] Add frontend type-check gate as a separate CI job (`npm run typecheck`).
- [ ] Add synthetic monitoring and alert routing validation in staging.
- [ ] Add rollback runbook and deployment verification checklist.

## Current status notes (2026-03-03)

- Fixed in this iteration:
  - Invalid TOML escape sequences in `pyproject.toml`.
  - Python syntax issues in ticket category assignment and dialogue tracker strings.
  - Frontend build pipeline blockers (Vite config alias, socket typing/import issues, Rollup optional binary).
- Still required before production:
  - Resolve runtime dependency/setup issues for backend startup in a clean environment.
  - Complete/replace placeholder API logic in critical flows.
  - Execute and pass true end-to-end tests in staging-like infra.
