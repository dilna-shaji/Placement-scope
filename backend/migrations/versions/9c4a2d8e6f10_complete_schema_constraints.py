"""Complete remaining model constraints and vacancy source width.

Revision ID: 9c4a2d8e6f10
Revises: 7a1c9d3e5b20
"""
from alembic import op
import sqlalchemy as sa


revision = "9c4a2d8e6f10"
down_revision = "7a1c9d3e5b20"
branch_labels = None
depends_on = None


def _foreign_keys(table):
    return {
        (tuple(fk.get("constrained_columns") or ()), fk.get("referred_table")): fk
        for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)
    }


def _has_orphans(query):
    return op.get_bind().execute(sa.text(query)).first() is not None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    student_fks = _foreign_keys("students")
    add_user_fk = (("user_id",), "users") not in student_fks
    add_resume_fk = (("resume_doc_id",), "documents") not in student_fks

    if add_user_fk and _has_orphans(
        "SELECT 1 FROM students s LEFT JOIN users u ON u.id = s.user_id "
        "WHERE s.user_id IS NOT NULL AND u.id IS NULL LIMIT 1"
    ):
        raise RuntimeError("Cannot add students.user_id foreign key: orphan user references exist.")
    if add_resume_fk and _has_orphans(
        "SELECT 1 FROM students s LEFT JOIN documents d ON d.id = s.resume_doc_id "
        "WHERE s.resume_doc_id IS NOT NULL AND d.id IS NULL LIMIT 1"
    ):
        raise RuntimeError("Cannot add students.resume_doc_id foreign key: orphan document references exist.")

    if add_user_fk or add_resume_fk:
        recreate = "always" if dialect == "sqlite" else "auto"
        with op.batch_alter_table("students", recreate=recreate) as batch_op:
            if add_user_fk:
                batch_op.create_foreign_key(
                    "fk_students_user", "users", ["user_id"], ["id"], ondelete="SET NULL"
                )
            if add_resume_fk:
                batch_op.create_foreign_key(
                    "fk_students_resume_doc", "documents", ["resume_doc_id"], ["id"], ondelete="SET NULL"
                )

    source_column = next(
        column for column in sa.inspect(bind).get_columns("vacancies") if column["name"] == "source"
    )
    if getattr(source_column["type"], "length", None) != 60:
        length_function = "LENGTH" if dialect == "sqlite" else "CHAR_LENGTH"
        too_long = bind.execute(
            sa.text(
                f"SELECT 1 FROM vacancies WHERE {length_function}(source) > 60 LIMIT 1"
            )
        ).first()
        if too_long:
            raise RuntimeError("Cannot set vacancies.source to 60 characters: longer values exist.")
        with op.batch_alter_table(
            "vacancies", recreate="always" if dialect == "sqlite" else "auto"
        ) as batch_op:
            batch_op.alter_column(
                "source",
                existing_type=source_column["type"],
                type_=sa.String(length=60),
                existing_nullable=source_column["nullable"],
            )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    length_function = "LENGTH" if dialect == "sqlite" else "CHAR_LENGTH"
    if bind.execute(
        sa.text(f"SELECT 1 FROM vacancies WHERE {length_function}(source) > 20 LIMIT 1")
    ).first():
        raise RuntimeError("Cannot shrink vacancies.source to 20 characters: longer values exist.")

    student_fks = _foreign_keys("students")
    drop_user_fk = (("user_id",), "users") in student_fks and student_fks[(("user_id",), "users")].get("name")
    drop_resume_fk = (
        (("resume_doc_id",), "documents") in student_fks
        and student_fks[(("resume_doc_id",), "documents")].get("name")
    )
    if drop_user_fk or drop_resume_fk:
        with op.batch_alter_table(
            "students", recreate="always" if dialect == "sqlite" else "auto"
        ) as batch_op:
            if drop_user_fk:
                batch_op.drop_constraint(drop_user_fk, type_="foreignkey")
            if drop_resume_fk:
                batch_op.drop_constraint(drop_resume_fk, type_="foreignkey")

    source_column = next(
        column for column in sa.inspect(bind).get_columns("vacancies") if column["name"] == "source"
    )
    if getattr(source_column["type"], "length", None) != 20:
        with op.batch_alter_table(
            "vacancies", recreate="always" if dialect == "sqlite" else "auto"
        ) as batch_op:
            batch_op.alter_column(
                "source",
                existing_type=source_column["type"],
                type_=sa.String(length=20),
                existing_nullable=source_column["nullable"],
            )
