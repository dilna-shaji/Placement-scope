import { useState } from 'react';
import { History, KeyRound, Lock, Pencil, Plus, Power, ShieldCheck, Unlock, UserCheck, UserX, Check } from 'lucide-react';
import { api, ApiError, qs } from '../../../lib/api';
import { useAuth } from '../../../context/AuthContext';
import { useUI } from '../../../context/UIContext';
import { Badge, Button, Card, ConfirmDialog, Drawer, Empty, ErrorNote, Field, Modal, PageHeader, SelectInput, Skeleton, StatusBadge, Tabs, TextArea, TextInput, useFetch } from '../../ui/kit';
import { CredentialsModal, type Credentials } from '../../common/CredentialsModal';
import { fmtDateTime, initials } from '../../../lib/format';
import type { Row } from '../../../types';

const ROLES = [['super_admin', 'Super Admin'], ['placement_director', 'Placement Director'], ['department_tpo', 'Department TPO / Faculty'], ['corporate_recruiter', 'Corporate Recruiter'], ['student_coordinator', 'Student Coordinator']];

/* ---------- create/edit user ---------- */
function UserForm({ user, onClose, onDone }: { user: Row | null; onClose: () => void; onDone: (c?: Credentials) => void }) {
  const { lookups } = useAuth();
  const { toast } = useUI();
  const [f, setF] = useState<Row>(user ? { ...user } : { role: 'department_tpo' });
  const [errs, setErrs] = useState<Record<string, string>>({}); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: React.ChangeEvent<any>) => setF((s) => ({ ...s, [k]: e.target.value }));
  const needDept = ['department_tpo', 'student_coordinator'].includes(f.role); const needCo = f.role === 'corporate_recruiter';
  const save = async () => {
    setBusy(true); setErrs({}); setMsg('');
    const body = { fullName: f.fullName, email: f.email, employeeId: f.employeeId, role: f.role, designation: f.designation, phone: f.phone, departmentId: needDept ? Number(f.departmentId) || null : null, companyId: needCo ? Number(f.companyId) || null : null };
    try {
      if (user) { await api.put(`/api/users/${user.id}`, body); toast('User updated'); onDone(); }
      else { const r = await api.post<{ credentials: Credentials }>('/api/users', body); onDone(r.credentials); }
    } catch (e) { setErrs((e as ApiError).fields || {}); setMsg((e as ApiError).message); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} title={user ? 'Edit user & role' : 'Create user'} subtitle={user ? undefined : 'A temporary password is generated and shown once.'} width="max-w-2xl"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>{user ? 'Save changes' : 'Create account'}</Button></>}>
      {msg && <div role="alert" className="mb-5 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{msg}</div>}
      <div className="grid sm:grid-cols-2 gap-5">
        <Field label="Full name" required error={errs.fullName}><TextInput value={f.fullName || ''} onChange={set('fullName')} /></Field>
        <Field label="E-mail / login ID" required error={errs.email}><TextInput type="email" disabled={!!user} value={f.email || ''} onChange={set('email')} /></Field>
        <Field label="Role" required error={errs.role} hint="The role stored here is the only source of authority."><SelectInput value={f.role} onChange={set('role')}>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</SelectInput></Field>
        {needDept && <Field label="Department scope" required error={errs.departmentId}><SelectInput value={f.departmentId || ''} onChange={set('departmentId')}><option value="">Select…</option>{lookups.departments?.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}</SelectInput></Field>}
        {needCo && <Field label="Company" required error={errs.companyId}><SelectInput value={f.companyId || ''} onChange={set('companyId')}><option value="">Select…</option>{lookups.companies?.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}</SelectInput></Field>}
        <Field label="Employee ID" error={errs.employeeId}><TextInput disabled={!!user} value={f.employeeId || ''} onChange={set('employeeId')} /></Field>
        <Field label="Designation"><TextInput value={f.designation || ''} onChange={set('designation')} /></Field>
        <Field label="Phone"><TextInput value={f.phone || ''} onChange={set('phone')} /></Field>
      </div>
    </Modal>
  );
}

/* ---------- approve request ---------- */
function ApproveModal({ req, onClose, onDone }: { req: Row; onClose: () => void; onDone: (c: Credentials) => void }) {
  const { lookups } = useAuth();
  const [role, setRole] = useState(req.requestedRole);
  const [dept, setDept] = useState(String(req.departmentId || '')); const [co, setCo] = useState(''); const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false); const [msg, setMsg] = useState('');
  const needDept = ['department_tpo', 'student_coordinator'].includes(role); const needCo = role === 'corporate_recruiter';
  const go = async () => {
    setBusy(true); setMsg('');
    try { const r = await api.post<{ credentials: Credentials }>(`/api/account-requests/${req.id}/approve`, { role, departmentId: needDept ? Number(dept) || null : null, companyId: Number(co) || null, createCompany: needCo && !co, note }); onDone(r.credentials); }
    catch (e) { setMsg((e as ApiError).message); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} title="Review & approve request" subtitle={`${req.fullName} · ${req.email}`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={go}><UserCheck className="w-4 h-4" />Approve & create account</Button></>}>
      <div className="rounded-2xl bg-canvas p-5 grid sm:grid-cols-2 gap-x-6 gap-y-3 text-[14px] mb-6">
        {[['Requested role', req.requestedRoleLabel], ['Department', req.departmentName], ['Designation', req.designation], ['Phone', req.phone], ['Staff ID', req.employeeId], ['Company', req.companyName], ['Company e-mail', req.companyEmail], ['Student ID', req.studentIdNo], ['Academic year', req.academicYear], ['Supervisor', req.facultySupervisor]].filter(([, v]) => v).map(([k, v]) => <div key={k}><p className="text-[12px] uppercase font-semibold text-mute">{k}</p><p className="font-medium">{v}</p></div>)}
        <div className="sm:col-span-2"><p className="text-[12px] uppercase font-semibold text-mute">Reason for access</p><p>{req.reason}</p></div>
      </div>
      <p className="text-[13.5px] text-mute mb-4">Verify the person’s identity first. The role you choose below — not the one requested — is what will be stored.</p>
      {msg && <div role="alert" className="mb-4 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{msg}</div>}
      <div className="grid sm:grid-cols-2 gap-5">
        <Field label="Assign role" required><SelectInput value={role} onChange={(e) => setRole(e.target.value)}>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</SelectInput></Field>
        {needDept && <Field label="Department scope" required><SelectInput value={dept} onChange={(e) => setDept(e.target.value)}><option value="">Select…</option>{lookups.departments?.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}</SelectInput></Field>}
        {needCo && <Field label="Company" hint={req.companyName ? `Leave empty to create “${req.companyName}” from the request.` : undefined}><SelectInput value={co} onChange={(e) => setCo(e.target.value)}><option value="">{req.companyName ? `Create “${req.companyName}”` : 'Select…'}</option>{lookups.companies?.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}</SelectInput></Field>}
        <Field label="Review note" className="sm:col-span-2"><TextArea value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Identity verified with HR on 11 Nov" /></Field>
      </div>
    </Modal>
  );
}

function PermissionMatrix() {
  const { toast } = useUI();
  const { data, loading, error, reload } = useFetch<{ roles: Row[]; catalogue: string[]; superAdminOnly: string[]; lockedForSuperAdmin: string[] }>('/api/roles');
  const [draft, setDraft] = useState<Record<number, string[]>>({}); const [busy, setBusy] = useState<number | null>(null);
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (loading || !data) return <Skeleton className="h-96" />;
  const groups = Array.from(new Set(data.catalogue.map((p) => p.split(':')[0])));
  const has = (r: Row, p: string) => (draft[r.id] ?? r.permissions).includes(p);
  const toggle = (r: Row, p: string) => { const cur = draft[r.id] ?? r.permissions; setDraft({ ...draft, [r.id]: cur.includes(p) ? cur.filter((x: string) => x !== p) : [...cur, p] }); };
  const save = async (r: Row) => { setBusy(r.id); try { await api.put(`/api/roles/${r.id}/permissions`, { permissions: draft[r.id] }); toast(`${r.label} permissions saved`); setDraft((d) => { const n = { ...d }; delete n[r.id]; return n; }); reload(); } catch (e) { toast((e as ApiError).message, 'error'); } finally { setBusy(null); } };
  return (
    <Card padded={false} className="overflow-hidden">
      <div className="p-5 border-b border-line"><h3 className="font-bold text-[17px]">Role permission matrix</h3><p className="text-[13.5px] text-mute">System-level permissions (marked <Lock className="inline w-3 h-3" />) can never be granted to non Super Admin roles. Changes apply to the next request.</p></div>
      <div className="overflow-auto max-h-[640px]"><table className="tbl w-full min-w-[900px]"><thead><tr><th>Permission</th>{data.roles.map((r) => <th key={r.id} className="text-center">{r.label}<br /><span className="normal-case font-normal">{r.userCount} user(s)</span></th>)}</tr></thead>
        <tbody>{groups.map((g) => (<>
          <tr key={g}><td colSpan={data.roles.length + 1} className="!bg-canvas !py-2 font-bold uppercase text-[12px] tracking-wider text-violet">{g.replace('_', ' ')}</td></tr>
          {data.catalogue.filter((p) => p.startsWith(g + ':')).map((p) => (
            <tr key={p}><td className="font-mono text-[13px]">{p} {data.superAdminOnly.includes(p) && <Lock className="inline w-3 h-3 text-coral" />}</td>
              {data.roles.map((r) => { const locked = r.name === 'super_admin' ? data.lockedForSuperAdmin.includes(p) : data.superAdminOnly.includes(p);
                return <td key={r.id} className="text-center"><input type="checkbox" className="w-[18px] h-[18px] accent-[#5146D8] disabled:opacity-40" checked={has(r, p)} disabled={locked} aria-label={`${r.label} ${p}`} onChange={() => toggle(r, p)} /></td>; })}</tr>))}</>))}
        </tbody></table></div>
      <div className="p-4 border-t border-line flex flex-wrap gap-3 bg-[#fbfaff]">{data.roles.filter((r) => draft[r.id]).map((r) => <Button key={r.id} size="sm" loading={busy === r.id} onClick={() => save(r)}><Check className="w-4 h-4" />Save {r.label}</Button>)}{!Object.keys(draft).length && <span className="text-[13.5px] text-mute">No unsaved changes.</span>}</div>
    </Card>
  );
}

export default function UserRoleView() {
  const { user: me } = useAuth();
  const { toast } = useUI();
  const [tab, setTab] = useState<'requests' | 'users' | 'roles'>('requests');
  const [rq, setRq] = useState('Pending Approval'); const [uq, setUq] = useState(''); const [uRole, setURole] = useState('');
  const reqs = useFetch<{ items: Row[] }>(`/api/account-requests${qs({ status: rq })}`);
  const pend = useFetch<{ items: Row[] }>('/api/account-requests?status=Pending Approval');
  const users = useFetch<{ items: Row[] }>(`/api/users${qs({ q: uq, role: uRole })}`);
  const [approve, setApprove] = useState<Row | null>(null); const [reject, setReject] = useState<Row | null>(null); const [rejNote, setRejNote] = useState('');
  const [edit, setEdit] = useState<Row | null | undefined>(undefined); const [cred, setCred] = useState<Credentials | null>(null);
  const [toggle, setToggle] = useState<Row | null>(null); const [resetU, setResetU] = useState<Row | null>(null); const [hist, setHist] = useState<{ u: Row; items: Row[] } | null>(null);

  const refresh = () => { reqs.reload(); pend.reload(); users.reload(); };
  const fail = (e: unknown) => toast((e as ApiError).message, 'error');

  return (
    <div className="space-y-7">
      <PageHeader title="Users & roles" subtitle="Approve account requests, assign roles and department scope, and control who can sign in." actions={<Button onClick={() => setEdit(null)}><Plus className="w-4 h-4" />Create user</Button>} />
      <Tabs value={tab} onChange={(t) => { setTab(t); refresh(); }} tabs={[{ id: 'requests', label: 'Account requests', count: pend.data?.items.length }, { id: 'users', label: 'Users' }, { id: 'roles', label: 'Roles & permissions' }]} />

      {tab === 'requests' && (
        <Card padded={false} className="overflow-hidden">
          <div className="p-5 border-b border-line flex gap-3"><SelectInput className="w-auto" value={rq} onChange={(e) => setRq(e.target.value)}><option>Pending Approval</option><option>Approved</option><option>Rejected</option></SelectInput></div>
          {reqs.error ? <div className="p-6"><ErrorNote message={reqs.error} onRetry={reqs.reload} /></div> : !reqs.data?.items.length ? <Empty title={`No ${rq.toLowerCase()} requests`} text="New requests from the sign-in page appear here." /> : (
            <div className="overflow-x-auto"><table className="tbl w-full min-w-[820px]"><thead><tr><th>Applicant</th><th>Requested</th><th>Department / company</th><th>Submitted</th><th>Status</th><th className="text-right">Actions</th></tr></thead>
              <tbody>{reqs.data.items.map((r) => <tr key={r.id}><td><p className="font-semibold">{r.fullName}</p><p className="text-[13px] text-mute">{r.email}</p></td><td><Badge tone="violet">{r.requestedRoleLabel}</Badge></td><td>{r.companyName || r.departmentName || '—'}</td><td className="text-mute">{fmtDateTime(r.createdAt)}</td><td><StatusBadge value={r.status} /></td>
                <td><div className="flex justify-end gap-2">{r.status === 'Pending Approval' ? <><Button size="sm" onClick={() => setApprove(r)}><UserCheck className="w-4 h-4" />Review</Button><Button size="sm" variant="danger" onClick={() => setReject(r)}><UserX className="w-4 h-4" />Reject</Button></> : <span className="text-[13px] text-mute">{r.reviewNote || '—'}</span>}</div></td></tr>)}</tbody></table></div>)}
        </Card>)}

      {tab === 'users' && (
        <Card padded={false} className="overflow-hidden">
          <div className="p-5 border-b border-line flex flex-wrap gap-3"><TextInput className="max-w-sm" placeholder="Search name, e-mail or staff ID…" value={uq} onChange={(e) => setUq(e.target.value)} />
            <SelectInput className="w-auto" value={uRole} onChange={(e) => setURole(e.target.value)}><option value="">All roles</option>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</SelectInput></div>
          {users.error ? <div className="p-6"><ErrorNote message={users.error} onRetry={users.reload} /></div> : (
            <div className="overflow-x-auto"><table className="tbl w-full min-w-[900px]"><thead><tr><th>User</th><th>Role</th><th>Scope</th><th>Last sign-in</th><th>Status</th><th className="text-right">Actions</th></tr></thead>
              <tbody>{users.data?.items.map((u) => <tr key={u.id}>
                <td><div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo to-violet text-white grid place-items-center font-bold text-[13px]">{initials(u.fullName)}</div><div><p className="font-semibold">{u.fullName}{u.id === me!.id && <span className="text-mute font-normal"> (you)</span>}</p><p className="text-[13px] text-mute">{u.email}</p></div></div></td>
                <td><Badge tone={u.role === 'super_admin' ? 'coral' : 'violet'}><ShieldCheck className="w-3.5 h-3.5" />{u.roleLabel}</Badge></td><td>{u.companyName || u.departmentName || 'Institution-wide'}</td><td className="text-mute">{fmtDateTime(u.lastLoginAt)}</td>
                <td><div className="flex gap-1.5 flex-wrap"><StatusBadge value={u.status} />{u.lockedNow && <Badge tone="coral"><Lock className="w-3 h-3" />Locked</Badge>}{u.mustChangePassword && <Badge tone="amber">Temp password</Badge>}</div></td>
                <td><div className="flex justify-end gap-1">
                  <button title="Edit role / scope" aria-label="Edit" onClick={() => setEdit(u)} className="p-2 rounded-lg text-mute hover:bg-indigo/10 hover:text-indigo"><Pencil className="w-4 h-4" /></button>
                  <button title="Reset credentials" aria-label="Reset credentials" onClick={() => setResetU(u)} className="p-2 rounded-lg text-mute hover:bg-indigo/10 hover:text-indigo"><KeyRound className="w-4 h-4" /></button>
                  {u.lockedNow && <button title="Unlock" aria-label="Unlock" onClick={async () => { try { await api.post(`/api/users/${u.id}/unlock`); toast('Account unlocked'); users.reload(); } catch (e) { fail(e); } }} className="p-2 rounded-lg text-mute hover:bg-aqua/15 hover:text-[#0e7a7c]"><Unlock className="w-4 h-4" /></button>}
                  <button title="History" aria-label="History" onClick={async () => { try { setHist({ u, items: (await api.get<{ items: Row[] }>(`/api/users/${u.id}/history`)).items }); } catch (e) { fail(e); } }} className="p-2 rounded-lg text-mute hover:bg-indigo/10 hover:text-indigo"><History className="w-4 h-4" /></button>
                  {u.id !== me!.id && <button title={u.status === 'active' ? 'Deactivate' : 'Activate'} aria-label="Toggle access" onClick={() => setToggle(u)} className={`p-2 rounded-lg text-mute ${u.status === 'active' ? 'hover:bg-coral/15 hover:text-[#c2412b]' : 'hover:bg-aqua/15 hover:text-[#0e7a7c]'}`}><Power className="w-4 h-4" /></button>}
                </div></td></tr>)}</tbody></table></div>)}
        </Card>)}

      {tab === 'roles' && <PermissionMatrix />}

      {approve && <ApproveModal req={approve} onClose={() => setApprove(null)} onDone={(c) => { setApprove(null); setCred(c); refresh(); }} />}
      {edit !== undefined && <UserForm user={edit} onClose={() => setEdit(undefined)} onDone={(c) => { setEdit(undefined); if (c) setCred(c); refresh(); }} />}
      <CredentialsModal cred={cred} onClose={() => setCred(null)} />
      <Modal open={!!reject} onClose={() => setReject(null)} title="Reject request" subtitle={reject?.email} width="max-w-lg" footer={<><Button variant="secondary" onClick={() => setReject(null)}>Cancel</Button><Button variant="danger" onClick={async () => { try { await api.post(`/api/account-requests/${reject!.id}/reject`, { note: rejNote }); toast('Request rejected'); setReject(null); setRejNote(''); refresh(); } catch (e) { fail(e); } }}>Reject request</Button></>}>
        <Field label="Reason (kept in the record)"><TextArea value={rejNote} onChange={(e) => setRejNote(e.target.value)} /></Field></Modal>
      <ConfirmDialog open={!!toggle} danger={toggle?.status === 'active'} title={toggle?.status === 'active' ? 'Deactivate account?' : 'Activate account?'} confirmLabel={toggle?.status === 'active' ? 'Deactivate' : 'Activate'}
        message={toggle?.status === 'active' ? `${toggle?.fullName} will be signed out immediately and cannot sign in until re-activated.` : `${toggle?.fullName} will be able to sign in again.`}
        onClose={() => setToggle(null)} onConfirm={async () => { try { await api.post(`/api/users/${toggle!.id}/status`, { status: toggle!.status === 'active' ? 'disabled' : 'active' }); toast('Access updated'); setToggle(null); refresh(); } catch (e) { fail(e); setToggle(null); } }} />
      <ConfirmDialog open={!!resetU} title="Reset credentials?" confirmLabel="Generate new password" message={`A new temporary password will be generated for ${resetU?.fullName} and existing sessions will end. The old password cannot be retrieved.`} onClose={() => setResetU(null)}
        onConfirm={async () => { try { const r = await api.post<{ credentials: Credentials }>(`/api/users/${resetU!.id}/reset-credentials`); setResetU(null); setCred(r.credentials); refresh(); } catch (e) { fail(e); setResetU(null); } }} />
      <Drawer open={!!hist} onClose={() => setHist(null)} title={`History · ${hist?.u.fullName ?? ''}`}>
        <ol className="space-y-4">{hist?.items.map((h) => <li key={h.id} className="border-l-2 border-violet/40 pl-4"><p className="font-semibold text-[14.5px]">{h.action}</p><p className="text-[13px] text-mute">{h.details || h.entityType} · {fmtDateTime(h.createdAt)}</p></li>)}{!hist?.items.length && <p className="text-mute">No history yet.</p>}</ol>
      </Drawer>
    </div>
  );
}
