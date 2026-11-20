import { useState } from 'react';
import { ArrowLeft, CheckCircle2, Send } from 'lucide-react';
import { api, ApiError } from '../../lib/api';
import { Button, Field, SelectInput, TextArea, TextInput } from '../ui/kit';
import { AuthLayout, Captcha, useAuthConfig } from './shared';

export function RequestAccountScreen({ back }: { back: () => void }) {
  const { cfg } = useAuthConfig();
  const [f, setF] = useState<Record<string, string>>({ requestedRole: '' });
  const [captcha, setCaptcha] = useState<Record<string, string> | null>(null);
  const [reset, setReset] = useState(0);
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState('');
  const set = (k: string) => (e: React.ChangeEvent<any>) => setF((s) => ({ ...s, [k]: e.target.value }));
  const role = f.requestedRole;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setErrs({});
    if (!captcha) return setError('Complete the security check.');
    setBusy(true);
    try { const r = await api.post<{ message: string }>('/api/auth/request-account', { ...f, captcha }); setDone(r.message); }
    catch (x) { const a = x as ApiError; setError(a.message); setErrs(a.fields || {}); setReset((n) => n + 1); setCaptcha(null); }
    finally { setBusy(false); }
  };

  if (done) return (
    <AuthLayout>
      <div className="text-center py-6">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-aqua/15 text-aqua grid place-items-center"><CheckCircle2 className="w-8 h-8" /></div>
        <h2 className="font-display font-extrabold text-[26px] mt-5">Request submitted</h2>
        <p className="text-mute mt-2">{done}</p>
        <p className="text-[14px] text-mute mt-4">Status: <b className="text-ink">Pending Approval</b>. You cannot sign in until a Super Admin verifies and approves your account.</p>
        <Button className="mt-7" onClick={back}>Back to sign in</Button>
      </div>
    </AuthLayout>
  );

  return (
    <AuthLayout wide>
      <button onClick={back} className="flex items-center gap-1.5 text-[14px] font-semibold text-indigo mb-4"><ArrowLeft className="w-4 h-4" />Back to sign in</button>
      <h2 className="font-display font-extrabold text-[28px]">Request a new account</h2>
      <p className="text-mute mt-1.5 mb-6">An administrator will verify your details and assign your role. Requesting a role does not grant it.</p>
      <form onSubmit={submit} className="grid sm:grid-cols-2 gap-5" noValidate>
        <Field label="Requested role" required error={errs.requestedRole} className="sm:col-span-2">
          <SelectInput value={role} onChange={set('requestedRole')}>
            <option value="">Select…</option>
            {cfg?.selfRegisterRoles.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </SelectInput>
        </Field>
        <Field label="Full name" required error={errs.fullName}><TextInput value={f.fullName || ''} onChange={set('fullName')} /></Field>
        <Field label={role === 'corporate_recruiter' ? 'Official e-mail' : 'Institutional e-mail'} required error={errs.email}><TextInput type="email" value={f.email || ''} onChange={set('email')} /></Field>
        {role !== 'corporate_recruiter' && (
          <Field label="Department" required error={errs.departmentId}>
            <SelectInput value={f.departmentId || ''} onChange={set('departmentId')}><option value="">Select…</option>{cfg?.departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</SelectInput>
          </Field>
        )}
        <Field label="Designation"><TextInput value={f.designation || ''} onChange={set('designation')} /></Field>
        <Field label="Contact number"><TextInput value={f.phone || ''} onChange={set('phone')} /></Field>
        {role === 'department_tpo' && <Field label="Employee / staff ID"><TextInput value={f.employeeId || ''} onChange={set('employeeId')} /></Field>}
        {role === 'corporate_recruiter' && <>
          <Field label="Company name" required error={errs.companyName}><TextInput value={f.companyName || ''} onChange={set('companyName')} /></Field>
          <Field label="Official company e-mail" required error={errs.companyEmail}><TextInput type="email" value={f.companyEmail || ''} onChange={set('companyEmail')} /></Field>
          <Field label="Company contact number"><TextInput value={f.companyPhone || ''} onChange={set('companyPhone')} /></Field>
        </>}
        {role === 'student_coordinator' && <>
          <Field label="Student ID" required error={errs.studentIdNo}><TextInput value={f.studentIdNo || ''} onChange={set('studentIdNo')} /></Field>
          <Field label="Academic year"><TextInput placeholder="2025-27" value={f.academicYear || ''} onChange={set('academicYear')} /></Field>
          <Field label="Faculty supervisor" required error={errs.facultySupervisor}><TextInput value={f.facultySupervisor || ''} onChange={set('facultySupervisor')} /></Field>
        </>}
        <Field label="Reason for access" required error={errs.reason} className="sm:col-span-2"><TextArea value={f.reason || ''} onChange={set('reason')} placeholder="Explain why you need access to PlacementHub." /></Field>
        <div className="sm:col-span-2">{cfg && <Captcha config={cfg.captcha} onChange={setCaptcha} resetKey={reset} />}</div>
        {error && <div role="alert" className="sm:col-span-2 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{error}</div>}
        <div className="sm:col-span-2"><Button type="submit" size="lg" loading={busy} className="w-full"><Send className="w-4 h-4" />Submit request</Button></div>
      </form>
    </AuthLayout>
  );
}
