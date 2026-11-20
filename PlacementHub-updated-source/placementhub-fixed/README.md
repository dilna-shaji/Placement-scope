# PlacementHub — College Placement Management

PlacementHub is an existing full-stack placement-management application built with React, TypeScript, Vite, Flask and SQLAlchemy. Its 20 modules cover common college placement workflows, including department-scoped access, student onboarding, vacancy verification and opportunity aggregation. Production readiness depends on deployment configuration and validation; see the audit notes below for verified checks and outstanding work.

---

## 1. System Architecture

```
   ┌─────────────────────────────────────────────────────────────────┐
   │                  React 19 + TypeScript SPA                      │
   │      (Vite, Tailwind CSS, Lucide Icons, Recharts, Motion)       │
   └──────────────────────────────┬──────────────────────────────────┘
                                  │ JSON REST API + SSE
                                  │ (Reverse Proxied via Vite / Nginx)
   ┌──────────────────────────────▼──────────────────────────────────┐
   │                   Python Flask 3 Backend                        │
   │          (SQLAlchemy, Argon2id, OpenPyXL, Waitress)             │
   └───────┬──────────────────────┬───────────────────────────┬──────┘
           │                      │                           │
           ▼                      ▼                           ▼
   ┌───────────────┐      ┌───────────────┐           ┌──────────────┐
   │  Persistence  │      │ Scam Detector │           │ Aggregation  │
   │  MySQL 8 /    │      │  & Risk Engine│           │   Pipeline   │
   │  SQLite DB    │      │ (Fraud & Red- │           │ (Greenhouse, │
   │               │      │  flag screen) │           │ Serper, ATS) │
   └───────────────┘      └───────────────┘           └──────────────┘
```

---

## 2. Key Modules & Institutional Roles

### 20 Integrated Institutional Modules
1. **Dashboard & KPIs:** Role-specific analytics, pipeline metrics, and recent activity.
2. **User & Role Management:** Account provisioning, password resets, and access control.
3. **Student Management:** Student profiles, CGPA, backlogs, Excel bulk import & export.
4. **Academic & Departments:** Department specializations, annual intake, and live placement rates.
5. **Company Management:** Corporate directory, hiring tiers, and MoU lifecycle tracking.
6. **Vacancies & Opportunities:** Job notification forms, eligibility rules, and approval workflow.
7. **Opportunity Collection & Aggregator:** Automated scraper pipeline and CSV/ATS feeds.
8. **Vacancy Verification & Approvals:** Pre-student approval workflow with scam risk badges.
9. **Company Outreach:** Institutional corporate communication log and follow-ups.
10. **Recruitment Drives:** On-campus and virtual drive scheduling and logistics.
11. **Student Applications:** Stage-by-stage selection funnel (Applied → Shortlisted → Selected).
12. **Internships:** Internship progress tracking and Pre-Placement Offer (PPO) conversion.
13. **Placements:** Accepted job offers, verified CTC packages, and verification letters.
14. **Analytics & Insights:** Cross-department placement percentage and historical trends.
15. **Reports & Exports:** Standardized placement reports in Excel and CSV.
16. **Notifications & Announcements:** In-app notification center with real-time SSE stream.
17. **Documents & Verification:** Student resumes, offer letters, and institutional certificates.
18. **Audit & Activity Logs:** Comprehensive tamper-evident audit logging for all transactions.
19. **Security & Privacy:** Active session management, lockout policies, and security signals.
20. **System Settings:** Institution profile, academic year configuration, and policy rules.

### Institutional Role Hierarchy
- **Super Admin (`super_admin`):** Full administrative authority, system configuration, audit logs.
- **Placement Director (`placement_director`):** Institutional placement oversight, corporate MoUs, vacancy verification.
- **Department TPO (`department_tpo`):** Department-scoped access; manages students and drives for their department only.
- **Corporate Recruiter (`corporate_recruiter`):** Scoped strictly to candidates who applied to their own job postings.
- **Student Coordinator (`student_coordinator`):** Assists with drives and student eligibility verification.
- **Department Faculty (`department_faculty`):** Read-only department analytics and student progress tracking.
- **Student (`student`):** View verified eligible vacancies, submit applications, track selection stage, withdraw applications.

---

## 3. Getting Started & Local Development

### Prerequisites
- **Node.js:** v18+ (v20 or v22 recommended)
- **Python:** v3.10+
- **Database:** SQLite (default for development) or MySQL 8.0+

### Step 1: Clone and Install Dependencies
```bash
# Frontend dependencies
npm install

# Backend dependencies
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

### Step 2: Configure Environment Variables
Create `backend/.env` with:
```ini
SECRET_KEY="replace-with-a-random-64-character-string"
DATABASE_URL="sqlite:///placementhub.db"
# For MySQL 8: DATABASE_URL="mysql+pymysql://user:password@localhost:3306/placementhub"
CAPTCHA_PROVIDER="local"
SERPER_API_KEY=""  # Optional: For Google Serper career search aggregation
PORT=5000
```

### Step 3: Initialize Database & Seed Roles
```bash
cd backend
python3 -m flask db upgrade
# Or initialize cleanly:
python3 -c "from app import create_app; from app.extensions import db; from app.cli import seed_rbac; a=create_app(); a.app_context().push(); db.create_all(); seed_rbac()"

# Create Super Admin account:
python3 -m flask create-superadmin --email admin@your-institution.edu --name "Super Administrator"
# The CLI prompts for a unique initial password and confirmation; do not put it in shell history.
cd ..
```

### Step 4: Run Development Server
```bash
npm run dev
```
The application will launch on `http://localhost:3000` with the Python API backend running on `http://127.0.0.1:5000`.

---

## 4. Bulk Student Onboarding via Excel / CSV

1. Navigate to **Students** (`/students`).
2. Click **Download Official Template** to obtain `students_import_template.xlsx`.
3. Fill in student records with columns:
   - `Roll No*` (Unique student roll number, e.g. `CSE2024-001`)
   - `Full Name*` (Student's complete name)
   - `Email*` (Institutional or personal e-mail)
   - `Phone` (10-digit mobile number)
   - `Department Code*` (Must match institutional department, e.g. `CSE`, `IT`, `ECE`)
   - `Batch*` (e.g. `2024-2026`)
   - `CGPA` (Numeric value between 0.00 and 10.00)
   - `Active Backlogs` (Integer >= 0)
   - `Skills` (Comma-separated skills, e.g. `Python, SQL, React`)
4. Click **Bulk Excel Import**, select the file, and toggle **Dry Run Validation Mode**.
5. Inspect the validation preview (Ready, Skipped duplicates, and line-by-line errors).
6. Click **Commit Import** to persist the records.

---

## 5. Web Scraping & Scam Detection Engine

The modular scraper pipeline gathers opportunities from verified ATS endpoints and web channels:
- **Greenhouse ATS Connector:** Parses job boards for enterprise employers.
- **Serper API Connector:** Discovers live company career portal postings.
- **Internshala & LinkedIn Connectors:** Aggregates public engineering, finance, and management listings.
- If selected external sources return no listings, the run records zero discovered/created opportunities; it does not manufacture sample vacancies.

### Scam Risk Classification
Every imported listing is evaluated by `scam_detector.py` before appearing in the placement cell dashboard:
- **Monetary Demands (+65 pts):** Registration fees, security deposits, caution money, or paid interviews flag listings as **High Risk**.
- **Suspicious Links (+35 pts):** URL shorteners (`bit.ly`, `tinyurl.com`) or Telegram/WhatsApp groups instead of career portals.
- **Free Webmail (+20 pts):** Personal mail addresses (`@gmail.com`) instead of corporate domains.
- **Unrealistic CTC (+20 pts):** Compensation promises > 45 LPA for campus entry roles.

All imported listings enter the database as `Draft` or `Pending Verification`. Only after a Placement Officer or TPO approves the listing does it become visible to eligible students.

---

## 6. Production Deployment Guide

### Deploying on Ubuntu 22.04 / 24.04 with MySQL 8 & Nginx

Before applying a migration to any existing database, take and verify a restorable backup, rehearse the upgrade on a staging copy, and review the migration output. Never drop or recreate an existing production database to resolve a migration mismatch.

#### 1. MySQL 8 Database Setup
```sql
CREATE DATABASE placementhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'placement_user'@'localhost' IDENTIFIED BY 'REPLACE_WITH_A_UNIQUE_RANDOM_PASSWORD';
GRANT ALL PRIVILEGES ON placementhub.* TO 'placement_user'@'localhost';
FLUSH PRIVILEGES;
```
Replace the placeholder with a unique secret and configure TLS before exposing the service publicly.

#### 2. Backend Systemd Service (`/etc/systemd/system/placementhub-api.service`)

Set `APP_ENV=production`, `SESSION_COOKIE_SECURE=true`, `CAPTCHA_PROVIDER=turnstile` and real Turnstile credentials in the protected backend `.env`. The backend refuses to start in production if secure session cookies are disabled. Keep Waitress bound to loopback; let the HTTPS reverse proxy be the only public entry point.

```ini
[Unit]
Description=PlacementHub WSGI Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/placementhub/backend
Environment="PATH=/var/www/placementhub/backend/venv/bin"
EnvironmentFile=/var/www/placementhub/backend/.env
ExecStart=/var/www/placementhub/backend/venv/bin/waitress-serve --listen=127.0.0.1:5000 --threads=8 app:create_app()
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 3. Build Frontend
```bash
npm run build
# Dist output will be in /var/www/placementhub/dist
```

#### 4. Nginx Virtual Host (`/etc/nginx/sites-available/placementhub`)
```nginx
server {
    listen 443 ssl;
    server_name placementhub.yourdomain.edu;
    ssl_certificate /etc/letsencrypt/live/placementhub.yourdomain.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/placementhub.yourdomain.edu/privkey.pem;

    root /var/www/placementhub/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/notifications/stream {
        proxy_pass http://127.0.0.1:5000/api/notifications/stream;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
    }
}

server {
    listen 80;
    server_name placementhub.yourdomain.edu;
    return 301 https://$host$request_uri;
}
```

---

## 7. Automated Test Suite

Run the full pytest suite:
```bash
pytest backend/tests
```
- The backend suite currently contains 52 automated tests covering authentication, RBAC scoping, department barriers, aggregation, scam detection, and import validation.

## 8. Current Audit Notes and Limits

The provided source archive was compared with the configured workspace: 97 non-secret source files were SHA-256 checked, with no missing files or mismatches. The archive included root and backend `.env` files with configured secret values. Those values are intentionally not reproduced here; rotate the exposed Gemini API key and Flask `SECRET_KEY`, and do not distribute either `.env` file. The source ignore rules now also exclude local databases, upload files, Python virtual environments, and bytecode.

Prioritized findings:
1. **Credential exposure:** Rotate secrets present in the shared archive. Use `backend/.env.example` only as a placeholder template and supply fresh production values outside source control.
2. **Fabricated aggregation records:** The previous zero-results fallback inserted hardcoded employer/job records as if discovered. It has been removed; empty feeds now create no vacancies.
3. **Production verification remains outstanding:** Fresh and previous-revision migrations passed on disposable SQLite databases, including row preservation, FK enforcement and model/schema comparison. MySQL connectivity, migrations against a real production schema, deployment, backup/restore, live third-party connectors, and full browser coverage were not verified. Do not treat the separate `SECURITY_REPORT.md` as a compliance certification or as evidence that those checks were performed.

Current checks run after these changes: 52 backend tests passed; TypeScript check and Vite production build passed. The build emits a Vite configuration-loader warning about `__dirname`; it does not fail the build.
