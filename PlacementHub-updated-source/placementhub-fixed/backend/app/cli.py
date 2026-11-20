"""CLI: flask seed-rbac | create-superadmin | seed-sample"""
import getpass
import random
from datetime import date, timedelta

import click

from .extensions import db
from .models import (Application, Company, Department, Internship, Permission, PlacementOffer, RecruitmentDrive, Role,
                     Student, User, UserRole, Vacancy, utcnow)
from .permissions import (ALL_PERMISSIONS, ROLE_DESCRIPTIONS, ROLE_LABELS, ROLE_PERMISSIONS, SUPER_ADMIN)
from .security import hash_password, password_problems

DEPARTMENTS = [("MKT", "Marketing"), ("FIN", "Finance"), ("HR", "HR"), ("OPS", "Operations"), ("BA", "Business Analytics")]


def seed_rbac(reset=False):
    perms = {p.code: p for p in Permission.query.all()}
    for code in ALL_PERMISSIONS:
        if code not in perms:
            perms[code] = Permission(code=code)
            db.session.add(perms[code])
    for name, label in ROLE_LABELS.items():
        role = Role.query.filter_by(name=name).first()
        fresh = role is None
        if fresh:
            role = Role(name=name, label=label, description=ROLE_DESCRIPTIONS[name])
            db.session.add(role)
        if fresh or reset:  # never overwrite grants an administrator has customised unless --reset
            role.permissions = [perms[c] for c in ROLE_PERMISSIONS[name]]
    for code, name in DEPARTMENTS:
        if not Department.query.filter_by(code=code).first():
            db.session.add(Department(code=code, name=name))
    db.session.commit()


def register_cli(app):
    @app.cli.command("seed-rbac")
    @click.option("--reset", is_flag=True, help="Reset role grants to the defaults in permissions.py")
    def _seed_rbac(reset):
        """Create roles, permissions and the five specialisation departments."""
        seed_rbac(reset)
        click.echo("Roles, permissions and departments are in place.")

    @app.cli.command("create-superadmin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt="Full name")
    @click.option("--password", default=None, help="Initial password (non-interactive)")
    def _create_sa(email, name, password):
        """Create the first Super Admin (the only way to bootstrap; there is no default account)."""
        seed_rbac()
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            raise click.ClickException("A user with that e-mail already exists.")
        if password:
            pw = password
        else:
            pw = getpass.getpass("Initial password: ")
            if pw != getpass.getpass("Repeat password: "):
                raise click.ClickException("Passwords do not match.")
        prob = password_problems(pw)
        if prob:
            raise click.ClickException(prob)
        u = User(email=email, full_name=name.strip(), password_hash=hash_password(pw), status="active",
                 must_change_password=False, password_changed_at=utcnow())
        u.assignment = UserRole(role=Role.query.filter_by(name=SUPER_ADMIN).one())
        db.session.add(u)
        db.session.commit()
        click.echo(f"Super Admin created: {email}")

    @app.cli.command("seed-sample")
    @click.option("--students", default=60)
    def _seed_sample(students):
        """OPTIONAL: generate clearly-labelled SAMPLE records (no user accounts) to explore the UI."""
        seed_rbac()
        if Company.query.filter_by(is_sample=True).first():
            raise click.ClickException("Sample data already exists.")
        rnd = random.Random(42)
        depts = Department.query.all()
        cos = []
        inds = ["Retail", "Banking", "Consulting", "Technology", "FMCG", "Manufacturing"]
        tiers = ["Super Dream (>20 LPA)", "Dream (12-20 LPA)", "Core Corporate", "Mass Recruiter"]
        for i in range(1, 9):
            c = Company(name=f"Sample Company {i:02d}", industry=rnd.choice(inds), tier=rnd.choice(tiers),
                        location=rnd.choice(["Bengaluru", "Mumbai", "Pune", "Chennai", "Hyderabad"]),
                        contact_name=f"Sample Contact {i:02d}", contact_email=f"hr{i:02d}@sample-company.invalid",
                        mou_status=rnd.choice(["Signed", "In Discussion", "None"]), about="SAMPLE DATA", is_sample=True)
            db.session.add(c)
            cos.append(c)
        db.session.flush()
        studs = []
        for i in range(1, students + 1):
            d = rnd.choice(depts)
            s = Student(roll_no=f"SMP-{i:04d}", name=f"Sample Student {i:03d}", email=f"sample.student{i:03d}@sample.invalid",
                        department_id=d.id, batch=rnd.choice(["2024-26", "2025-27"]), cgpa=round(rnd.uniform(5.8, 9.4), 2),
                        active_backlogs=rnd.choice([0, 0, 0, 1]), skills=rnd.sample(["Excel", "SQL", "Power BI", "Negotiation", "Python", "Branding"], 3),
                        status="Unplaced", is_sample=True)
            db.session.add(s)
            studs.append(s)
        db.session.flush()
        vacs = []
        for i, c in enumerate(cos):
            for k in range(2):
                v = Vacancy(title=f"Sample {rnd.choice(['Analyst', 'Associate', 'Trainee'])} {i + 1}-{k + 1}", company_id=c.id,
                            ctc_lpa=round(rnd.uniform(5, 24), 1), min_cgpa=6.5, max_backlogs=0, openings=rnd.randint(2, 8),
                            eligible_departments=[d.code for d in rnd.sample(depts, 3)], locations=[c.location],
                            application_deadline=date.today() + timedelta(days=rnd.randint(5, 40)), status="Active",
                            description="SAMPLE DATA", is_sample=True)
                db.session.add(v)
                vacs.append(v)
        db.session.flush()
        for v in vacs:
            for s in rnd.sample(studs, 6):
                if s.cgpa >= 6.5 and s.active_backlogs == 0 and s.department.code in v.eligible_departments \
                        and not Application.query.filter_by(student_id=s.id, vacancy_id=v.id).first():
                    st = rnd.choice(["Applied", "Shortlisted", "Technical", "HR", "Selected", "Rejected"])
                    db.session.add(Application(student_id=s.id, vacancy_id=v.id, stage=st, is_sample=True))
                    if st == "Selected" and s.status != "Placed":
                        o = PlacementOffer(student_id=s.id, company_id=v.company_id, designation=v.title, ctc_lpa=v.ctc_lpa,
                                           base_lpa=round(v.ctc_lpa * .8, 1), offer_accepted=True, verified=True,
                                           signed_date=date.today() - timedelta(days=rnd.randint(1, 240)),
                                           location=v.company.location, is_sample=True)
                        db.session.add(o)
                        db.session.flush()
                        o.offer_ref = f"SMP-OFR-{o.id:04d}"
                        s.status = "Placed"
        for s in rnd.sample(studs, min(12, len(studs))):
            db.session.add(Internship(student_id=s.id, company_name=rnd.choice(cos).name, stipend_per_month=15000, duration_months=2,
                                      progress_percent=rnd.choice([20, 55, 80, 100]), status="Ongoing", is_sample=True))
        for c in cos[:4]:
            db.session.add(RecruitmentDrive(title=f"Sample Drive – {c.name}", company_id=c.id, is_sample=True,
                                            date=date.today() + timedelta(days=rnd.randint(2, 30)), venue="Seminar Hall"))
        db.session.commit()
        click.echo("Sample data created. Every sample row is flagged is_sample=true and named 'Sample …'.")
