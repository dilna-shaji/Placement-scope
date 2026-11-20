# Fixes in this revision (no UI / UX / design changes)

## Login → "session expired"
* `backend/app/auth.py` – the session cookie was marked `Secure` whenever `SESSION_COOKIE_SECURE=true`, even on plain
  `http://localhost`. Browsers silently drop such cookies, so a *correct* login looked like an instantly expired session.
  `Secure` is now only set when the request really arrives over HTTPS (or via a proxy sending `X-Forwarded-Proto: https`).
* `backend/app/auth.py` – the idle-timeout lookup can no longer raise on a bad value in the settings table.
* `src/context/AuthContext.tsx` – after login the app confirms the browser kept the cookie. If it did not, you now get a
  precise message instead of being bounced back with "session expired". The expiry banner is only shown to a user who
  really was signed in (and no longer sets state inside a state updater).
* `src/components/layout/TopBar.tsx` – notification polling / SSE no longer restarts on every auth-context update.

## CAPTCHA
* `backend/app/security.py` – challenge lifetime 5 → 15 min, answer ignores case/spaces, clearer messages.
* `src/components/auth/shared.tsx` – out-of-order CAPTCHA responses can no longer pair a picture with the wrong id.

## Backend bugs
* **Database migration was out of date** – `flask db upgrade` created a schema missing student/vacancy/drive columns and the
  `aggregation_runs` table (→ "Unexpected server error" on students, vacancies, drives, aggregation).
  New migration `7a1c9d3e5b20_sync_schema_with_models.py` (safe to run on databases created either way).
* **Aggregation pipeline crashed** (`re` never imported) and `beautifulsoup4` was missing from `requirements.txt`;
  one failing source no longer aborts a run; imported `job_type` values are normalised to the values the form accepts.
* **Notification stream (SSE)** – sent a forbidden `Connection` header (rejected by waitress), emitted named events the UI
  never listened for, and queried the DB after the request context had ended.
* **Permission leaks** – `/api/recruiter/candidates` returned every applicant to any role with `applications:read`;
  `/api/recruiter/candidates/<id>/stage` let any role (incl. students) change any application; students could set their own
  application stage via `PUT /api/applications/<id>`; TPOs could bulk-import students into other departments;
  faculty saw every department; students/faculty always saw an empty drives list.
* Crashes on empty values (null CGPA/backlogs), bad `page`/`pageSize`, duplicate-apply race, score validation.
* Upload folder is now resolved relative to `backend/`, not the current working directory.

## Tests
`backend/tests/test_fixes.py` covers the above. Run `pytest backend/tests`.

## After updating
```
pip install -r backend/requirements.txt
cd backend && python3 -m flask db upgrade
```
Restart both servers, then hard-refresh the browser (Ctrl+Shift+R).
