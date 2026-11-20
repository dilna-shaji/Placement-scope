"""Document & certificate upload with server-side validation."""
import os
import secrets

from flask import Blueprint, current_app, g, jsonify, request, send_file
from flask import abort

from .auth import can, require_auth
from .errors import ApiError
from .extensions import db
from .models import Document, Student
from .permissions import SUPER_ADMIN
from .permissions import DIRECTOR, TPO
from .resources import students_scope
from .services import audit

bp = Blueprint("files", __name__, url_prefix="/api")
ALLOWED = {".pdf": (b"%PDF",), ".png": (b"\x89PNG",), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
           ".docx": (b"PK\x03\x04",)}
DOC_TYPES = ["Resume", "Offer Letter", "Internship Certificate", "Marksheet", "ID Proof", "Company MoU", "Other"]
FULL = (SUPER_ADMIN, DIRECTOR)


def _scoped_docs(u):
    q = Document.query
    if u.role_name in FULL:
        return q
    ids = students_scope(db.session.query(Student.id), u)
    return q.filter(Document.student_id.in_(ids))


def _dump(d):
    out = d.to_dict()
    out["studentName"] = d.student.name if d.student else None
    out["rollNo"] = d.student.roll_no if d.student else None
    return out


@bp.get("/documents")
@require_auth("documents:read")
def list_docs():
    q = _scoped_docs(g.user)
    if request.args.get("docType"):
        q = q.filter(Document.doc_type == request.args["docType"])
    if request.args.get("q"):
        q = q.filter(Document.title.ilike(f"%{request.args['q']}%"))
    return jsonify({"items": [_dump(d) for d in q.order_by(Document.created_at.desc()).limit(500)], "docTypes": DOC_TYPES})


@bp.post("/documents")
@require_auth("documents:write")
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        raise ApiError("Choose a file to upload.", 422, {"file": "Required"})
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED:
        raise ApiError("Allowed file types: PDF, PNG, JPG, DOCX.", 422, {"file": "Unsupported file type"})
    max_b = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    data = f.read(max_b + 1)
    if len(data) > max_b:
        raise ApiError(f"File exceeds {current_app.config['MAX_UPLOAD_MB']} MB.", 413)
    if not any(data.startswith(sig) for sig in ALLOWED[ext]):
        raise ApiError("File content does not match its extension.", 422, {"file": "Corrupt or mismatched file"})
    title = (request.form.get("title") or os.path.splitext(f.filename)[0]).strip()[:160]
    dtype = request.form.get("docType", "Other")
    if dtype not in DOC_TYPES:
        raise ApiError("Unknown document type.", 422, {"docType": "Invalid"})
    sid = request.form.get("studentId")
    if sid:
        if not sid.isdigit() or not students_scope(Student.query, g.user).filter(Student.id == int(sid)).first():
            raise ApiError("Student not found in your scope.", 404)
    elif g.user.role_name not in FULL:
        raise ApiError("Select the student this document belongs to.", 422, {"studentId": "Required"})
    os.makedirs(current_app.config["UPLOAD_DIR"], exist_ok=True)
    stored = secrets.token_hex(16) + ext  # never trust the client's file name for storage
    with open(os.path.join(current_app.config["UPLOAD_DIR"], stored), "wb") as fh:
        fh.write(data)
    d = Document(title=title, doc_type=dtype, student_id=int(sid) if sid else None, stored_name=stored,
                 original_name=os.path.basename(f.filename)[:190], mime=f.mimetype or "", size_bytes=len(data),
                 uploaded_by_id=g.user.id)
    db.session.add(d)
    db.session.commit()
    audit("Uploaded document", "document", d.id, d.title)
    return jsonify(_dump(d)), 201


def _get(did):
    d = _scoped_docs(g.user).filter(Document.id == did).first()
    if not d:
        raise ApiError("Document not found.", 404)
    return d


@bp.get("/documents/<int:did>/file")
@require_auth("documents:read")
def download(did):
    d = _get(did)
    path = os.path.join(current_app.config["UPLOAD_DIR"], d.stored_name)
    if not os.path.isfile(path):
        abort(404)
    audit("Downloaded document", "document", d.id, d.title)
    return send_file(os.path.abspath(path), as_attachment=True, download_name=d.original_name or d.stored_name)


@bp.post("/documents/<int:did>/verify")
@require_auth("documents:write")
def verify(did):
    if g.user.role_name not in FULL + (TPO,):
        raise ApiError("You may not verify documents.", 403, code="forbidden")
    d = _get(did)
    d.verified = bool((request.get_json(silent=True) or {}).get("verified", True))
    db.session.commit()
    audit("Verified document" if d.verified else "Unverified document", "document", d.id, d.title)
    return jsonify(_dump(d))


@bp.delete("/documents/<int:did>")
@require_auth("documents:delete")
def delete(did):
    d = _get(did)
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_DIR"], d.stored_name))
    except OSError:
        pass
    db.session.delete(d)
    db.session.commit()
    audit("Deleted document", "document", did, d.title)
    return jsonify({"ok": True})
