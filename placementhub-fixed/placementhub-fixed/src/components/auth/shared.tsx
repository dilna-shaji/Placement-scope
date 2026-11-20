import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { motion } from 'motion/react';
import { GraduationCap, RefreshCw, ShieldCheck, Users, BarChart3, Lock } from 'lucide-react';
import { api } from '../../lib/api';
import { AnimatedBackground } from '../common/AnimatedBackground';
import { Field, TextInput } from '../ui/kit';

export interface AuthConfig {
  captcha: { provider: 'turnstile' | 'local'; siteKey: string | null };
  selfRegisterRoles: { value: string; label: string }[];
  portalRoles: { value: string; label: string }[];
  departments: { id: number; code: string; name: string }[];
}
export function useAuthConfig() {
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { api.get<AuthConfig>('/api/auth/config').then(setCfg).catch((e) => setErr(e.message)); }, []);
  return { cfg, err };
}

export function AuthLayout({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return (
    <div className="h-screen w-screen overflow-y-auto relative bg-midnight">
      <AnimatedBackground />
      <div className="relative min-h-full grid lg:grid-cols-[1.05fr_1fr]">
        <section className="hidden lg:flex flex-col justify-between p-12 xl:p-16 text-white">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet to-aqua grid place-items-center shadow-lg shadow-violet/40"><GraduationCap className="w-6 h-6" /></div>
            <span className="font-display font-extrabold text-[24px]">PlacementHub</span>
          </div>
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .7 }}>
            <h1 className="font-display font-extrabold text-[44px] xl:text-[52px] leading-[1.05]">Every placement,<br /><span className="bg-gradient-to-r from-lime via-aqua to-violet bg-clip-text text-transparent">one secure workspace.</span></h1>
            <p className="mt-5 text-[17px] text-white/70 max-w-lg">Students, companies, drives and offers — managed by the people who are authorised to see them, and only them.</p>
            <ul className="mt-9 space-y-4 max-w-md">
              {[[ShieldCheck, 'Administrator-approved roles', 'Access is granted by verification, never by self-selection.'], [Users, 'Department-scoped data', 'Faculty and recruiters only see their own records.'], [BarChart3, 'Live placement analytics', 'Computed from your institution’s records.']].map(([I, t, d]: any, i) => (
                <motion.li key={t} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: .3 + i * .12 }} className="flex gap-4">
                  <div className="w-10 h-10 rounded-xl bg-white/10 border border-white/15 grid place-items-center shrink-0"><I className="w-5 h-5 text-lime" /></div>
                  <div><p className="font-semibold">{t}</p><p className="text-white/60 text-[14px]">{d}</p></div>
                </motion.li>
              ))}
            </ul>
          </motion.div>
          <p className="text-[13px] text-white/40 flex items-center gap-2"><Lock className="w-3.5 h-3.5" />Sessions are protected with HttpOnly cookies, CSRF tokens and audit logging.</p>
        </section>
        <section className="flex items-center justify-center p-5 sm:p-8">
          <motion.div initial={{ opacity: 0, y: 28, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: .5 }}
            className={`w-full ${wide ? 'max-w-3xl' : 'max-w-[480px]'} bg-white rounded-[28px] shadow-2xl shadow-black/30 p-7 sm:p-9 my-6`}>
            {children}
          </motion.div>
        </section>
      </div>
    </div>
  );
}

declare global { interface Window { turnstile?: any } }

/** Real CAPTCHA: Cloudflare Turnstile when configured, otherwise the server-verified local adapter (dev only). */
export function Captcha({ config, onChange, resetKey }: { config: AuthConfig['captcha']; onChange: (v: Record<string, string> | null) => void; resetKey: number }) {
  const box = useRef<HTMLDivElement>(null);
  const [local, setLocal] = useState<{ id: string; svg: string } | null>(null);
  const [answer, setAnswer] = useState('');
  const [failed, setFailed] = useState('');
  const seq = useRef(0);

  const loadLocal = useCallback(() => {
    const mine = ++seq.current;  // ignore out-of-order responses so the picture and its id always match what the user types against
    setAnswer(''); onChange(null); setFailed('');
    api.get<{ id: string; svg: string }>('/api/auth/captcha')
      .then((c) => { if (mine === seq.current) setLocal(c); })
      .catch((e) => { if (mine === seq.current) setFailed(e.message); });
  }, [onChange]);

  useEffect(() => {
    if (config.provider === 'local') { loadLocal(); return; }
    if (!config.siteKey) { setFailed('CAPTCHA site key is not configured on the server.'); return; }
    onChange(null);
    const render = () => {
      if (!box.current || !window.turnstile) return;
      box.current.innerHTML = '';
      window.turnstile.render(box.current, { sitekey: config.siteKey, callback: (t: string) => onChange({ token: t }), 'expired-callback': () => onChange(null) });
    };
    if (window.turnstile) render();
    else {
      const s = document.createElement('script');
      s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      s.async = true; s.onload = render; document.head.appendChild(s);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.provider, config.siteKey, resetKey]);

  if (config.provider === 'turnstile') return <div><div ref={box} />{failed && <p className="text-[13px] text-[#c2412b]">{failed}</p>}</div>;
  return (
    <Field label="Security check" hint="Type the characters shown. Development CAPTCHA adapter — use Cloudflare Turnstile in production.">
      <div className="flex items-center gap-3">
        <div className="rounded-xl overflow-hidden border border-line shrink-0 h-[50px] w-[160px] bg-canvas" dangerouslySetInnerHTML={{ __html: local?.svg ?? '' }} aria-label="CAPTCHA image" />
        <button type="button" onClick={loadLocal} aria-label="New CAPTCHA" className="p-2.5 rounded-xl border border-line hover:bg-slate-50"><RefreshCw className="w-4 h-4" /></button>
        <TextInput value={answer} autoComplete="off" placeholder="Characters" onChange={(e) => { setAnswer(e.target.value); onChange(local && e.target.value ? { id: local.id, answer: e.target.value } : null); }} />
      </div>
      {failed && <p className="text-[13px] text-[#c2412b] mt-1">{failed}</p>}
    </Field>
  );
}
