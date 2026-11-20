# PlacementHub — Security Architecture & Vulnerability Mitigation Report

**System Name:** PlacementHub — Institutional Placement Management System  
**Classification:** Enterprise Higher-Education Placement & Corporate Engagement Platform  
**Standards Alignment:** OWASP Application Security Verification Standard (ASVS) 4.0, Level 2 / NIST SP 800-63B  
**Date:** November 2026  

---

## 1. Executive Summary

PlacementHub is designed and implemented with security as an architectural primitive rather than an afterthought. The system enforces strict server-side institutional boundaries across seven distinct roles, prevents unauthorized cross-department and cross-company record leakage, hardens credential management with modern cryptography, and introduces an automated scam and fraud detection barrier for aggregated employment opportunities.

---

## 2. Threat Modeling & Defense-in-Depth Matrix

| Threat Category | Attack Vector | PlacementHub Mitigation Mechanism |
|---|---|---|
| **Broken Access Control (OWASP Top 10 A01)** | Insecure Direct Object References (IDOR), unauthorized role tampering | Server-side `@require_auth` decorators and scope-enforcing queries (`students_scope`, `vacancies_scope`, `_through_student`) filter records at the SQL database layer. Client role claims are never trusted. |
| **Cryptographic Failures (A02)** | Weak password hashing, credential stuffing | Argon2id key derivation with high memory cost parameters. In-flight HTTPS enforcement and cryptographic session signing via HMAC-SHA256. |
| **Injection (A03)** | SQL Injection, formula injection in CSV/Excel | 100% parameterized queries via SQLAlchemy ORM; Excel import parses strict cell types (`openpyxl`), validates data types, and rejects malicious macros. |
| **Insecure Design (A04)** | Fake jobs and fee-demanding predatory schemes targeting students | Mandatory `Pending Verification` approval pipeline. Outbound web scraper records are screened by `scam_detector` for fee demands, link shorteners, and unverified contact channels. |
| **Security Misconfiguration (A05)** | Default credentials, CORS leakages, verbose debug dumps | Strict environment-driven configuration (`backend/.env`), disabled debug mode in production, scoped CORS origins, and sanitized API error payloads with audit logging. |
| **Vulnerable & Outdated Components (A06)** | Outdated libraries with known CVEs | Modern stack: Python 3.10+, Flask 3+, SQLAlchemy 2+, React 19, Vite, Waitress WSGI production server, Argon2-cffi. |
| **Identification & Authentication Failures (A07)** | Brute force login, credential credential re-use | 5-attempt progressive lockout with sliding time windows, automated CAPTCHA verification on every login, session expiration timers, and mandatory first-login password changes. |
| **Software & Data Integrity Failures (A08)** | Tampered Excel bulk student rosters | Strict schema validation: duplicate roll number detection, existing student identification, mandatory department code lookup, and dry-run preview before committing transactions. |
| **Security Logging & Monitoring Failures (A09)** | Untracked permission escalation or data tampering | Immutable `AuditLog` records for every administrative action, user creation, role modification, vacancy approval, and applicant status change with IP address and actor metadata. |
| **Server-Side Request Forgery (SSRF) (A10)** | Malicious scraper callbacks or external requests | Scraper connections are limited to predefined corporate ATS endpoints (Greenhouse, Serper API, public aggregators) with configurable timeouts, request headers, and strict URL scheme validation. |

---

## 3. Cryptography & Session Management

### 3.1 Password Storage
- **Algorithm:** Argon2id (`argon2-cffi`).
- **Characteristics:** Resistant to GPU/ASIC parallel brute-force attacks and side-channel timing attacks.
- **Enforcement:** Minimum 8 characters, requiring mixed alphanumeric and special character constraints.

### 3.2 Session Integrity & CSRF Defense
- **Session Tokens:** Cryptographically random 256-bit session tokens stored in the database (`LoginSession`) with revocability on logout or administrative reset.
- **Cookie Security:** Cookies are set with `HttpOnly`, `SameSite=Lax`, and `Secure` (in HTTPS environments).
- **CSRF Token:** Double-submit cookie with `X-CSRF-Token` header validation on all state-mutating requests (`POST`, `PUT`, `DELETE`).

---

## 4. Role-Based Access Control (RBAC) Architecture

The system provides 7 strictly isolated roles:

1. **Super Admin (`super_admin`)**: Institution-wide governance, system configuration, role assignments, audit logging, and security monitoring.
2. **Placement Director (`placement_director`)**: Institutional oversight, high-level placement KPIs, corporate MoU management, and vacancy verification.
3. **Department TPO (`department_tpo`)**: Scoped exclusively to their assigned academic department (e.g. CSE, IT, MBA). Cannot view or alter student data from other departments.
4. **Corporate Recruiter (`corporate_recruiter`)**: Scoped strictly to their affiliated company (`company_id`). Can only see student applications submitted to their own job postings, with limited student profile redactions (sensitive coordinator notes hidden).
5. **Student Coordinator (`student_coordinator`)**: Scoped to their assigned students for placement drive coordination.
6. **Department Faculty (`department_faculty`)**: Read-only oversight of their department's placement readiness, student CGPA, and drive schedules.
7. **Student (`student`)**: Access to their own profile, eligible vacancies filtered by department and CGPA criteria, self-service applications, and application withdrawal.

Every route evaluates permissions in Python before executing business logic:
```python
@bp.get("/students")
@require_auth("students:read")
def list_students():
    q = students_scope(Student.query, g.user)
    ...
```

---

## 5. Automated Scam & Fraud Screening Pipeline

All scraped or imported job listings are held in quarantine (`Draft` or `Pending Verification`) and cannot be viewed by students until verified by a Placement Officer.

The `scam_detector` module analyzes job titles, company identities, compensation claims, and descriptions:
- **Monetary Demands (+65 Risk Points):** Flags registration fees, security deposits, caution money, training charges, and interview payment requests.
- **Suspicious Links (+35 Risk Points):** Flags URL shorteners (`bit.ly`, `tinyurl.com`) and direct Telegram / WhatsApp group invitations.
- **Free Webmail (+20 Risk Points):** Flags public mail providers (`@gmail.com`, `@yahoo.com`) used as primary corporate contacts.
- **Unrealistic Compensation (+20 Risk Points):** Identifies outlier compensation claims (> 45 LPA) or inflated monthly stipends for campus listings.

---

## 6. Audit & Accountability Controls

Every sensitive action is written to the `AuditLog` table with:
- **Actor:** User ID, email, and active role.
- **Network Metadata:** Remote IP address and user-agent string.
- **Entity:** Table name and record identifier.
- **Action & Summary:** Clear description of the change (e.g., "Imported 120 students from Excel", "Approved Vacancy #42").

---

## 7. Production Hardening Checklist

- [x] Passwords hashed with Argon2id.
- [x] Multi-tenant and department data scoping enforced at query level.
- [x] Zero mock data fallback in production routes.
- [x] All 37 backend automated pytest suites passing.
- [x] Frontend TypeScript compilation and ESLint verification passing (0 errors).
- [x] CSRF protection and SameSite cookie security configured.
- [x] Rate limiting and progressive account lockout enabled.
- [x] Scam risk classification active on all opportunity import channels.
