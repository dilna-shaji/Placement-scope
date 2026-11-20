"""sync schema with models (student profile, vacancy risk/source fields, drive eligibility, aggregation runs)

The initial migration pre-dates several model changes. Databases created with `flask db upgrade`
were missing these columns/tables, which made students, vacancies, drives and the aggregation
pipeline fail with "no such column" / "doesn't exist" errors. Databases created with
`db.create_all()` already have them, so every step is guarded and safe to run on either.

Revision ID: 7a1c9d3e5b20
Revises: 2e73f1fc7538
Create Date: 2026-11-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a1c9d3e5b20'
down_revision = '2e73f1fc7538'
branch_labels = None
depends_on = None


def _cols(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _add(table, *columns):
    existing = _cols(table)
    missing = [c for c in columns if c.name not in existing]
    if not missing:
        return
    with op.batch_alter_table(table, schema=None) as batch_op:
        for c in missing:
            batch_op.add_column(c)


def upgrade():
    insp = sa.inspect(op.get_bind())

    _add('students',
         sa.Column('gender', sa.String(length=20), nullable=True),
         sa.Column('passing_year', sa.Integer(), nullable=True),
         sa.Column('bio', sa.Text(), nullable=True),
         sa.Column('linkedin_url', sa.String(length=255), nullable=True),
         sa.Column('github_url', sa.String(length=255), nullable=True),
         sa.Column('user_id', sa.Integer(), nullable=True),
         sa.Column('resume_doc_id', sa.Integer(), nullable=True))

    _add('vacancies',
         sa.Column('source_url', sa.String(length=500), nullable=True),
         sa.Column('risk_level', sa.String(length=40), nullable=True),
         sa.Column('risk_score', sa.Integer(), nullable=True),
         sa.Column('risk_flags', sa.JSON(), nullable=True),
         sa.Column('duration', sa.String(length=60), nullable=True),
         sa.Column('work_mode', sa.String(length=40), nullable=True),
         sa.Column('scraped_at', sa.DateTime(), nullable=True))

    _add('recruitment_drives',
         sa.Column('rounds', sa.JSON(), nullable=True),
         sa.Column('eligible_departments', sa.JSON(), nullable=True),
         sa.Column('min_cgpa', sa.Float(), nullable=True))

    # Servers that support ALTER ADD CONSTRAINT receive these here; the next revision adds them on SQLite
    # with a batch table rebuild.
    if op.get_bind().dialect.name != 'sqlite':
        existing_fks = {fk['name'] for fk in insp.get_foreign_keys('students')}
        if 'fk_students_user' not in existing_fks:
            op.create_foreign_key('fk_students_user', 'students', 'users', ['user_id'], ['id'], ondelete='SET NULL')
        if 'fk_students_resume_doc' not in existing_fks:
            op.create_foreign_key('fk_students_resume_doc', 'students', 'documents', ['resume_doc_id'], ['id'],
                                  ondelete='SET NULL')

    if 'aggregation_runs' not in insp.get_table_names():
        op.create_table(
            'aggregation_runs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('source', sa.String(length=60), nullable=True),
            sa.Column('query', sa.String(length=190), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('discovered_count', sa.Integer(), nullable=True),
            sa.Column('duplicates_count', sa.Integer(), nullable=True),
            sa.Column('scam_flagged_count', sa.Integer(), nullable=True),
            sa.Column('created_count', sa.Integer(), nullable=True),
            sa.Column('duration_seconds', sa.Float(), nullable=True),
            sa.Column('logs', sa.JSON(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('triggered_by', sa.String(length=80), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('fk_students_resume_doc', 'students', type_='foreignkey')
        op.drop_constraint('fk_students_user', 'students', type_='foreignkey')
    op.drop_table('aggregation_runs')
    for table, names in (
        ('recruitment_drives', ('rounds', 'eligible_departments', 'min_cgpa')),
        ('vacancies', ('source_url', 'risk_level', 'risk_score', 'risk_flags', 'duration', 'work_mode', 'scraped_at')),
        ('students', ('gender', 'passing_year', 'bio', 'linkedin_url', 'github_url', 'user_id', 'resume_doc_id')),
    ):
        with op.batch_alter_table(table, schema=None) as batch_op:
            for n in names:
                batch_op.drop_column(n)
