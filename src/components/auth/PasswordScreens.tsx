import { useState } from 'react';
import { ArrowLeft, KeyRound, MailCheck } from 'lucide-react';
import { api, ApiError } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import type { AuthUser } from '../../types';
import { Button, Field, TextInput } from '../ui/kit';
import { AuthLayout, Captcha, useAuthConfig } from './shared';

const Err = ({ m }: { m: string }) => m ? <div role="alert" className="rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{m}</div> : null;
const RULES = 'At least 10 characters with upper and lower case letters, a number and a symbol.';

export function ForgotPasswordScreen({ back }: { back: () => void }) {
  const { cfg } = useAuthConfig();
  const [email, setEmail] = useState('');
  const [captcha, setCaptcha] = useState<Record<string, string> | null>(null);
  const [reset, setReset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr('');
    if (!captcha) return setErr('Complete the security check.');
    setBusy(true);
    try { setMsg((await api.post<{ message: string }>('/api/auth/forgot', { email, captcha })).message); }
    catch (x) { setErr((x as ApiError).message); setReset((n) => n + 1); setCaptcha(null); }
    finally { setBusy(false); }
  };
  return (
    <AuthLayout>
      <button onClick={back} className="flex items-center gap-1.5 text-[14px] font-semibold text-indigo mb-4"><ArrowLeft className="w-4 h-4" />Back to sign in</button>
      {msg ? (
        <div className="text-center py-4"><div className="w-16 h-16 mx-auto rounded-2xl bg-aqua/15 text-aqua grid place-items-center"><MailCheck className="w-8 h-8" /></div>
          <h2 className="font-display font-extrabold text-[26px] mt-5">Check your inbox</h2><p className="text-mute mt-2">{msg}</p></div>
      ) : (
        <form onSubmit={submit} className="space-y-5" noValidate>
          <h2 className="font-display font-extrabold text-[28px]">Reset your password</h2>
          <p className="text-mute -mt-2">Enter your account e-mail. If it is active, we will send a one-time link valid for 30 minutes.</p>
          <Field label="Institutional e-mail" required><TextInput type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          {cfg && <Captcha config={cfg.captcha} onChange={setCaptcha} resetKey={reset} />}
          <Err m={err} />
          <Button type="submit" size="lg" loading={busy} className="w-full">Send reset link</Button>
        </form>
      )}
    </AuthLayout>
  );
}

export function ResetPasswordScreen({ token, done }: { token: string; done: () => void }) {
  const [p1, setP1] = useState(''); const [p2, setP2] = useState('');
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(''); const [ok, setOk] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr('');
    if (p1 !== p2) return setErr('Passwords do not match.');
    setBusy(true);
    try { await api.post('/api/auth/reset', { token, newPassword: p1 }); setOk(true); }
    catch (x) { setErr((x as ApiError).message); } finally { setBusy(false); }
  };
  return (
    <AuthLayout>
      {ok ? (
        <div className="text-center py-4"><h2 className="font-display font-extrabold text-[26px]">Password updated</h2><p className="text-mute mt-2">You can now sign in with your new password.</p><Button className="mt-6" onClick={done}>Go to sign in</Button></div>
      ) : (
        <form onSubmit={submit} className="space-y-5" noValidate>
          <h2 className="font-display font-extrabold text-[28px]">Choose a new password</h2>
          <Field label="New password" required hint={RULES}><TextInput type="password" autoComplete="new-password" value={p1} onChange={(e) => setP1(e.target.value)} /></Field>
          <Field label="Confirm password" required><TextInput type="password" autoComplete="new-password" value={p2} onChange={(e) => setP2(e.target.value)} /></Field>
          <Err m={err} />
          <Button type="submit" size="lg" loading={busy} className="w-full">Update password</Button>
        </form>
      )}
    </AuthLayout>
  );
}

/** Shown right after login when the account still uses an administrator-issued temporary password. */
export function ForceChangePasswordScreen() {
  const { user, setUser, logout } = useAuth();
  const [cur, setCur] = useState(''); const [p1, setP1] = useState(''); const [p2, setP2] = useState('');
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr('');
    if (p1 !== p2) return setErr('Passwords do not match.');
    setBusy(true);
    try { const r = await api.post<{ user: AuthUser }>('/api/auth/change-password', { currentPassword: cur, newPassword: p1 }); setUser(r.user); }
    catch (x) { setErr((x as ApiError).message); } finally { setBusy(false); }
  };
  return (
    <AuthLayout>
      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo to-violet text-white grid place-items-center"><KeyRound className="w-7 h-7" /></div>
      <h2 className="font-display font-extrabold text-[28px] mt-5">Set your own password</h2>
      <p className="text-mute mt-1.5 mb-6">Hello {user?.fullName}. You are using a temporary password, so you must choose a new one before continuing.</p>
      <form onSubmit={submit} className="space-y-5" noValidate>
        <Field label="Temporary password" required><TextInput type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} /></Field>
        <Field label="New password" required hint={RULES}><TextInput type="password" autoComplete="new-password" value={p1} onChange={(e) => setP1(e.target.value)} /></Field>
        <Field label="Confirm new password" required><TextInput type="password" autoComplete="new-password" value={p2} onChange={(e) => setP2(e.target.value)} /></Field>
        <Err m={err} />
        <Button type="submit" size="lg" loading={busy} className="w-full">Save and continue</Button>
        <button type="button" onClick={logout} className="w-full text-center text-[14px] text-mute hover:text-ink">Sign out</button>
      </form>
    </AuthLayout>
  );
}
