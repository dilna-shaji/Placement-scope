# PlacementHub Security Review Notes

**Review date:** 2026-11-13  
**Scope:** Source review and existing backend tests, with targeted fixes for production session cookies and Greenhouse URL fetching. This is not a penetration test or an OWASP ASVS/NIST compliance assessment.

## Findings

| # | Severity | Status | Finding |
|---|---|---|---|
| 1 | HIGH | Action required | The uploaded source archive contains configured secrets in root `.env` and `backend/.env` files. The Gemini API key and Flask `SECRET_KEY` values are intentionally not reproduced. Rotate both credentials and do not redistribute those files. The updated source archive excludes `.env` files. |
| 2 | MEDIUM | Fixed | Serper search results were selected by a substring check and fetched without host validation or redirect restrictions, allowing server-side requests to untrusted destinations. Discovery now accepts only HTTPS URLs on the exact Greenhouse job-board hosts, rejects non-default ports/userinfo, and disables redirects. |
| 3 | HIGH | Fixed | The production example exposed Waitress on all interfaces and allowed session cookies without `Secure`. Production startup now requires `SESSION_COOKIE_SECURE=true`; the deployment example binds Waitress to loopback behind the TLS proxy. |

## Observed Controls

- Passwords are hashed with Argon2id; session tokens are random, stored hashed, revocable, and checked for idle and absolute expiry.
- State-changing authenticated requests require a session-bound CSRF header token. Session cookies use `HttpOnly` and `SameSite=Lax`; `Secure` is enabled when the request uses HTTPS and production configuration requires it.
- Authentication includes CAPTCHA verification, per-IP failure throttling, and progressive account lockout. These are login controls, not evidence of rate limiting on every API endpoint.
- Permission checks and resource-scoped queries are enforced on the backend. Existing tests cover selected role, department, company, and application-stage boundaries.
- Document uploads enforce an extension allowlist, content signatures, and a configured size limit. These checks do not constitute malware scanning or comprehensive file-format validation.
- Aggregated opportunities are held for verification. Empty external feeds no longer create hardcoded sample vacancies.

## Verification Limits

The application test suite runs in an isolated in-memory SQLite configuration. Fresh and previous-revision migrations, row preservation, foreign-key enforcement, downgrade/re-upgrade, and model/schema comparison were separately verified on disposable SQLite databases. MySQL migrations on an existing schema, production infrastructure, backups, live third-party connectors, full browser behavior, and deployment were not verified. SQL injection, XSS, and all IDOR paths were not exhaustively penetration-tested. Do not interpret the controls listed above as proof of compliance or complete security.
