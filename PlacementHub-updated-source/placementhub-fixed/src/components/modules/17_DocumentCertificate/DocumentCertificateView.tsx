import { useRef, useState } from 'react';
import { BadgeCheck, Download, FileUp, Trash2, FileText } from 'lucide-react';
import { api, ApiError, qs } from '../../../lib/api';
import { useAuth } from '../../../context/AuthContext';
import { useUI } from '../../../context/UIContext';
import { Badge, Button, Card, ConfirmDialog, Empty, ErrorNote, Field, Modal, PageHeader, SelectInput, TextInput, useFetch } from '../../ui/kit';
import { fmtDate } from '../../../lib/format';
import type { Row } from '../../../types';

const mb = (b: number) => (b / 1048576 >= 1 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export default function DocumentCertificateView() {
  const { user, can, lookups } = useAuth();
  const { toast } = useUI();
  const [type, setType] = useState(''); const [q, setQ] = useState('');
  const { data, loading, error, reload } = useFetch<{ items: Row[]; docTypes: string[] }>(`/api/documents${qs({ docType: type, q })}`);
  const [open, setOpen] = useState(false); const [f, setF] = useState<Row>({ docType: 'Resume' }); const [file, setFile] = useState<File | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState(''); const [del, setDel] = useState<Row | null>(null);
  const ref = useRef<HTMLInputElement>(null);
  const canVerify = ['super_admin', 'placement_director', 'department_tpo'].includes(user!.role);
  const upload = async () => {
    if (!file) return setErr('Choose a file.');
    setBusy(true); setErr('');
    const fd = new FormData(); fd.append('file', file); fd.append('docType', f.docType); if (f.title) fd.append('title', f.title); if (f.studentId) fd.append('studentId', f.studentId);
    try { await api.upload('/api/documents', fd); toast('Document uploaded'); setOpen(false); setFile(null); setF({ docType: 'Resume' }); reload(); } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };
  const dl = async (d: Row) => { const r = await fetch(`/api/documents/${d.id}/file`, { credentials: 'same-origin' }); if (!r.ok) return toast('Download failed', 'error'); const b = await r.blob(); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = d.originalName || d.title; a.click(); };
  return (
    <div className="space-y-7">
      <PageHeader title="Documents & certificates" subtitle="Resumes, offer letters and certificates. Files are type-checked on upload and only visible within your scope." actions={can('documents:write') && <Button onClick={() => setOpen(true)}><FileUp className="w-4 h-4" />Upload document</Button>} />
      <Card padded={false} className="overflow-hidden">
        <div className="p-5 border-b border-line flex flex-wrap gap-3"><TextInput className="max-w-sm" placeholder="Search title…" value={q} onChange={(e) => setQ(e.target.value)} /><SelectInput className="w-auto" value={type} onChange={(e) => setType(e.target.value)}><option value="">All types</option>{data?.docTypes.map((t) => <option key={t}>{t}</option>)}</SelectInput></div>
        {error ? <div className="p-6"><ErrorNote message={error} onRetry={reload} /></div> : !loading && !data?.items.length ? <Empty title="No documents" text="Uploaded files appear here." /> : (
          <div className="overflow-x-auto"><table className="tbl w-full min-w-[760px]"><thead><tr><th>Document</th><th>Type</th><th>Student</th><th>Size</th><th>Uploaded</th><th>Status</th><th className="text-right">Actions</th></tr></thead>
            <tbody>{data?.items.map((d) => <tr key={d.id}><td><div className="flex items-center gap-3"><div className="w-9 h-9 rounded-xl bg-indigo/10 text-indigo grid place-items-center"><FileText className="w-4 h-4" /></div><span className="font-semibold">{d.title}</span></div></td><td><Badge tone="violet">{d.docType}</Badge></td><td>{d.studentName ? `${d.studentName} (${d.rollNo})` : 'General'}</td><td className="text-mute">{mb(d.sizeBytes)}</td><td className="text-mute">{fmtDate(d.createdAt)}</td>
              <td>{d.verified ? <Badge tone="lime"><BadgeCheck className="w-3.5 h-3.5" />Verified</Badge> : <Badge tone="amber">Unverified</Badge>}</td>
              <td><div className="flex justify-end gap-1"><button aria-label="Download" title="Download" onClick={() => dl(d)} className="p-2 rounded-lg text-mute hover:bg-indigo/10 hover:text-indigo"><Download className="w-4 h-4" /></button>
                {canVerify && <button aria-label="Verify" title={d.verified ? 'Mark unverified' : 'Verify'} onClick={async () => { try { await api.post(`/api/documents/${d.id}/verify`, { verified: !d.verified }); reload(); } catch (e) { toast((e as ApiError).message, 'error'); } }} className="p-2 rounded-lg text-mute hover:bg-aqua/15 hover:text-[#0e7a7c]"><BadgeCheck className="w-4 h-4" /></button>}
                {can('documents:delete') && <button aria-label="Delete" title="Delete" onClick={() => setDel(d)} className="p-2 rounded-lg text-mute hover:bg-coral/15 hover:text-[#c2412b]"><Trash2 className="w-4 h-4" /></button>}</div></td></tr>)}</tbody></table></div>)}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Upload document" subtitle="PDF, PNG, JPG or DOCX up to 5 MB" width="max-w-xl" footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button loading={busy} onClick={upload}>Upload</Button></>}>
        {err && <div role="alert" className="mb-4 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{err}</div>}
        <div className="space-y-5"><Field label="File" required><button type="button" onClick={() => ref.current?.click()} className="w-full input text-left text-mute">{file ? file.name : 'Choose file…'}</button><input ref={ref} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <Field label="Title"><TextInput value={f.title || ''} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Type"><SelectInput value={f.docType} onChange={(e) => setF({ ...f, docType: e.target.value })}>{data?.docTypes.map((t) => <option key={t}>{t}</option>)}</SelectInput></Field>
          <Field label="Student" hint={user!.role === 'super_admin' || user!.role === 'placement_director' ? 'Optional for institution-level documents' : undefined} required={!['super_admin', 'placement_director'].includes(user!.role)}><SelectInput value={f.studentId || ''} onChange={(e) => setF({ ...f, studentId: e.target.value })}><option value="">— None —</option>{lookups.students?.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</SelectInput></Field></div>
      </Modal>
      <ConfirmDialog open={!!del} danger title="Delete document?" confirmLabel="Delete" message={`“${del?.title}” will be permanently removed.`} onClose={() => setDel(null)} onConfirm={async () => { try { await api.del(`/api/documents/${del!.id}`); toast('Document deleted'); setDel(null); reload(); } catch (e) { toast((e as ApiError).message, 'error'); setDel(null); } }} />
    </div>
  );
}
