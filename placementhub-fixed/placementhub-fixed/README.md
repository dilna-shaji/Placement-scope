# PlacementHub – Complete Institutional Placement Management System

PlacementHub is a full-stack, enterprise-grade Placement Management System tailored for universities, autonomous colleges, and higher-education institutions. It unifies the entire corporate recruitment lifecycle across 20 specialized modules with multi-department RBAC, real persistent database storage (MySQL 8 and SQLite), automated student Excel onboarding, and an integrated job aggregation and scam-screening pipeline.

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
python3 -m flask create-superadmin --email admin@placementhub.edu --name "Super Administrator" --password "Admin@12345678"
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

#### 1. MySQL 8 Database Setup
```sql
CREATE DATABASE placementhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'placement_user'@'localhost' IDENTIFIED BY 'Strong_DB_Password!2026';
GRANT ALL PRIVILEGES ON placementhub.* TO 'placement_user'@'localhost';
FLUSH PRIVILEGES;
```

#### 2. Backend Systemd Service (`/etc/systemd/system/placementhub-api.service`)
```ini
[Unit]
Description=PlacementHub WSGI Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/placementhub/backend
Environment="PATH=/var/www/placementhub/backend/venv/bin"
EnvironmentFile=/var/www/placementhub/backend/.env
ExecStart=/var/www/placementhub/backend/venv/bin/waitress-serve --port=5000 --threads=8 app:create_app()
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
    listen 80;
    server_name placementhub.yourdomain.edu;

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
```

---

## 7. Automated Test Suite

Run the full pytest suite:
```bash
pytest backend/tests
```
- Total tests: 37 automated unit and integration tests covering Authentication, RBAC scoping, Department barriers, Aggregation deduplication, Scam detection heuristics, and Excel import validation.
