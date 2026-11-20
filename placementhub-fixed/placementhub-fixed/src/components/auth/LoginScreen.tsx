import { useState } from 'react';
import { Eye, EyeOff, LogIn } from 'lucide-react';
import { ApiError } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import { Button, Field, SelectInput, TextInput } from '../ui/kit';
import { AuthLayout, Captcha, useAuthConfig } from './shared';

export function LoginScreen({ go }: { go: (s: 'request' | 'forgot') => void }) {
  const { login, sessionExpired } = useAuth();
  const { cfg, err: cfgErr } = useAuthConfig();
  const [f, setF] = useState({ identifier: '', password: '', portalRole: '', remember: false });
  const [captcha, setCaptcha] = useState<Record<string, string> | null>(null);
  const [reset, setReset] = useState(0);
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!f.portalRole) return setError('Select the portal you want to sign in to.');
    if (!captcha) return setError('Complete the security check.');
    setBusy(true);
    try { await login({ ...f, captcha }); }
    catch (x) { setError((x as ApiError).message); setReset((n) => n + 1); setCaptcha(null); }
    finally { setBusy(false); }
  };

  return (
    <AuthLayout>
      <h2 className="font-display font-extrabold text-[30px]">Welcome back</h2>
      <p className="text-mute mt-1.5 mb-7">Sign in with your institutional account.</p>
      {sessionExpired && <div role="status" className="mb-5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 text-[14px]">Your session expired. Please sign in again.</div>}
      {cfgErr && <div role="alert" className="mb-5 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{cfgErr}</div>}
      <form onSubmit={submit} className="space-y-5" noValidate>
        <Field label="Login ID / Institutional e-mail" required>
          <TextInput autoComplete="username" value={f.identifier} onChange={(e) => setF({ ...f, identifier: e.target.value })} placeholder="name@institution.edu" />
        </Field>
        <Field label="Password" required>
          <div className="relative">
            <TextInput type={show ? 'text' : 'password'} autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} className="pr-12" />
            <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'} className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-mute hover:text-ink">{show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button>
          </div>
        </Field>
        <Field label="Portal role" required hint="Selects which workspace you intend to open. Your permissions always come from your approved account.">
          <SelectInput value={f.portalRole} onChange={(e) => setF({ ...f, portalRole: e.target.value })}>
            <option value="">Select your role…</option>
            {cfg?.portalRoles.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </SelectInput>
        </Field>
        {cfg && <Captcha config={cfg.captcha} onChange={setCaptcha} resetKey={reset} />}
        <div className="flex items-center justify-between text-[14px]">
          <label className="flex items-center gap-2.5 cursor-pointer"><input type="checkbox" className="w-4 h-4 accent-[#5146D8]" checked={f.remember} onChange={(e) => setF({ ...f, remember: e.target.checked })} />Remember me</label>
          <button type="button" onClick={() => go('forgot')} className="font-semibold text-indigo hover:underline">Forgot password?</button>
        </div>
        {error && <div role="alert" className="rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{error}</div>}
        <Button type="submit" size="lg" loading={busy} disabled={!cfg} className="w-full"><LogIn className="w-4 h-4" />Sign in</Button>
      </form>
      <p className="text-center text-[14.5px] text-mute mt-7">Need access? <button onClick={() => go('request')} className="font-semibold text-indigo hover:underline">Request new account</button></p>
    </AuthLayout>
  );
}
