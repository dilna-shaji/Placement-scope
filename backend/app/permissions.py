"""CENTRAL permission configuration. The only place where roles are mapped to permissions.

Permission codes are "<resource>:<action>". Roles are seeded into the database from this file
(`flask seed-rbac`); the Super Admin can later adjust the non-locked ones from the UI.
"""

SUPER_ADMIN = "super_admin"
DIRECTOR = "placement_director"
TPO = "department_tpo"
RECRUITER = "corporate_recruiter"
COORDINATOR = "student_coordinator"
FACULTY = "department_faculty"
STUDENT = "student"

ROLE_LABELS = {
    SUPER_ADMIN: "Super Admin",
    DIRECTOR: "Placement Director",
    TPO: "Department TPO / Placement Officer",
    RECRUITER: "Corporate Recruiter",
    COORDINATOR: "Student Coordinator",
    FACULTY: "Department Faculty",
    STUDENT: "Student",
}
ROLE_DESCRIPTIONS = {
    SUPER_ADMIN: "Full system-level access, accounts, security and configuration.",
    DIRECTOR: "Institution-wide placement operations, analytics and reporting.",
    TPO: "Department-scoped placement coordination for assigned department only.",
    RECRUITER: "Own company profile, vacancies, drives and shared applicants only.",
    COORDINATOR: "Assigned students, schedules, applications and internship follow-ups.",
    FACULTY: "Department academic performance, verified records and student progress.",
    STUDENT: "Personal profile, eligible job search, applications, interviews, offers and documents.",
}
ROLES = list(ROLE_LABELS)

# Roles a person may *request* during self-registration. Super Admin / Director are never self-service.
SELF_REGISTERABLE = [TPO, RECRUITER, COORDINATOR, FACULTY, STUDENT]

RESOURCES = ["students", "companies", "vacancies", "outreach", "drives", "applications",
             "internships", "placements", "documents", "departments"]
ACTIONS = ["read", "write", "delete"]

SPECIAL = [
    "dashboard:view", "analytics:view", "reports:view", "notifications:read", "notifications:send",
    "vacancies:verify", "vacancies:import", "users:manage", "account_requests:manage",
    "roles:configure", "audit:view", "security:manage", "settings:manage",
]

ALL_PERMISSIONS = [f"{r}:{a}" for r in RESOURCES for a in ACTIONS] + SPECIAL

# Permissions that can never be removed from the Super Admin (prevents lock-out).
LOCKED_FOR_SUPER_ADMIN = {"users:manage", "account_requests:manage", "roles:configure",
                          "security:manage", "settings:manage", "audit:view", "dashboard:view"}
# Permissions that may never be granted to a non Super Admin role.
SUPER_ADMIN_ONLY = {"users:manage", "account_requests:manage", "roles:configure",
                    "security:manage", "settings:manage"}

_DIRECTOR_EXCLUDE = SUPER_ADMIN_ONLY | {"audit:view"}

ROLE_PERMISSIONS = {
    SUPER_ADMIN: set(ALL_PERMISSIONS),
    DIRECTOR: set(ALL_PERMISSIONS) - _DIRECTOR_EXCLUDE,
    TPO: {
        "dashboard:view", "analytics:view", "reports:view", "notifications:read",
        "students:read", "students:write", "departments:read",
        "vacancies:read", "applications:read", "applications:write",
        "internships:read", "internships:write", "placements:read",
        "drives:read", "documents:read", "documents:write",
    },
    RECRUITER: {
        "dashboard:view", "notifications:read",
        "companies:read", "companies:write",
        "vacancies:read", "vacancies:write",
        "drives:read", "applications:read", "applications:write",
        "students:read",
    },
    COORDINATOR: {
        "dashboard:view", "notifications:read",
        "students:read", "vacancies:read", "drives:read",
        "applications:read", "applications:write",
        "internships:read", "internships:write",
    },
    FACULTY: {
        "dashboard:view", "notifications:read", "reports:view",
        "students:read", "departments:read", "vacancies:read",
        "applications:read", "internships:read", "placements:read",
    },
    STUDENT: {
        "dashboard:view", "notifications:read",
        "students:read", "vacancies:read", "drives:read",
        "applications:read", "applications:write",
        "internships:read", "placements:read",
        "documents:read", "documents:write",
    },
}

# Frontend navigation catalogue is derived from these permission codes (see frontend/src/navigation.ts).
MODULE_PERMISSION = {
    "dashboard": "dashboard:view", "user-roles": "users:manage", "students": "students:read",
    "academic-departments": "departments:read", "companies": "companies:read",
    "vacancies": "vacancies:read", "opportunity-import": "vacancies:import",
    "vacancy-verification": "vacancies:verify", "company-outreach": "outreach:read",
    "recruitment-drives": "drives:read", "application-tracking": "applications:read",
    "internships": "internships:read", "placements": "placements:read", "analytics": "analytics:view",
    "reports-export": "reports:view", "notifications": "notifications:read",
    "documents": "documents:read", "audit-logs": "audit:view", "security-privacy": "security:manage",
    "system-settings": "settings:manage",
}
