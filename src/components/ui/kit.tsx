import { AnimatePresence, animate, motion, useReducedMotion } from 'motion/react';
import { Loader2, X, AlertTriangle, Inbox, ArrowUpRight } from 'lucide-react';
import { cloneElement, isValidElement, useCallback, useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type ReactElement, type ReactNode } from 'react';
import { cn } from '../../lib/format';
import { api, ApiError } from '../../lib/api';
import { AnimatedBackground } from '../common/AnimatedBackground';

/* ------------------------------------------------------------------ data hook */
export function useFetch<T>(url: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!!url);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!url) return;
    let live = true;
    setLoading(true);
    api.get<T>(url).then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e: ApiError) => { if (live) setError(e.message); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, tick, ...deps]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, reload, setData };
}

/* ------------------------------------------------------------------ buttons & badges */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'; size?: 'sm' | 'md' | 'lg'; loading?: boolean };
export function Button({ variant = 'primary', size = 'md', loading, className, children, disabled, ...p }: BtnProps) {
  const v = {
    primary: 'btn-primary text-white shadow-md shadow-indigo/25',
    secondary: 'bg-white text-ink border border-line hover:border-violet/50 hover:bg-[#faf9ff]',
    ghost: 'text-ink/80 hover:bg-indigo/8 hover:text-indigo',
    danger: 'bg-coral/10 text-[#c2412b] hover:bg-coral hover:text-white border border-coral/30',
    success: 'bg-aqua/15 text-[#0e7a7c] hover:bg-aqua hover:text-white border border-aqua/40',
  }[variant];
  const s = { sm: 'px-3 py-1.5 text-[13px] rounded-lg', md: 'px-4 py-2.5 text-[14px] rounded-xl', lg: 'px-6 py-3.5 text-[15px] rounded-xl' }[size];
  return (
    <button {...p} disabled={disabled || loading}
      className={cn('inline-flex items-center justify-center gap-2 font-semibold transition-all disabled:opacity-55 disabled:cursor-not-allowed active:scale-[.98]', v, s, className)}>
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  );
}

const tones: Record<string, string> = {
  indigo: 'bg-indigo/10 text-indigo', violet: 'bg-violet/12 text-[#6a4ad8]', aqua: 'bg-aqua/15 text-[#0e7a7c]',
  coral: 'bg-coral/15 text-[#c2412b]', lime: 'bg-lime/45 text-[#476a0e]', slate: 'bg-slate-100 text-slate-600', amber: 'bg-amber-100 text-amber-800',
};
export function Badge({ tone = 'slate', children, dot }: { tone?: keyof typeof tones | string; children: ReactNode; dot?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold whitespace-nowrap', tones[tone] || tones.slate)}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}{children}
    </span>
  );
}
const statusTone: Record<string, string> = {
  Placed: 'aqua', Active: 'aqua', Approved: 'aqua', Signed: 'aqua', Completed: 'aqua', Selected: 'aqua', Success: 'aqua', Sent: 'indigo', active: 'aqua', Verified: 'aqua',
  'In Process': 'violet', Upcoming: 'violet', Ongoing: 'violet', Shortlisted: 'violet', Replied: 'aqua', 'In Discussion': 'amber',
  'Pending Verification': 'amber', 'Pending Approval': 'amber', Pending: 'amber', Warning: 'amber', Draft: 'slate', Applied: 'slate', 'Follow-up': 'amber', Postponed: 'amber',
  Unplaced: 'coral', Rejected: 'coral', Failed: 'coral', disabled: 'coral', Terminated: 'coral', 'Opted Out': 'slate', Closed: 'slate', Archived: 'slate', 'Live Today': 'lime', 'PPO Converted': 'lime',
};
export const StatusBadge = ({ value }: { value: string }) => <Badge tone={statusTone[value] || 'slate'} dot>{value}</Badge>;

/* ------------------------------------------------------------------ cards, headers */
export function Card({ children, className, hover, padded = true, ...rest }: { children: ReactNode; className?: string; hover?: boolean; padded?: boolean } & React.HTMLAttributes<HTMLDivElement>) {
  return <div {...rest} className={cn('card', hover && 'card-hover', padded && 'p-6', className)}>{children}</div>;
}

export function PageHeader({ title, subtitle, actions, hero }: { title: string; subtitle?: string; actions?: ReactNode; hero?: boolean }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .4 }}
      className={cn('relative overflow-hidden rounded-3xl', hero ? 'p-8 lg:p-10 text-white' : '')}>
      {hero && <AnimatedBackground />}
      <div className="relative flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className={cn('font-display font-extrabold text-[28px] sm:text-[34px] leading-tight', hero ? 'text-white' : 'text-ink')}>{title}</h1>
          {subtitle && <p className={cn('mt-1.5 text-[15px] sm:text-[16px] max-w-3xl', hero ? 'text-white/75' : 'text-mute')}>{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
      </div>
    </motion.div>
  );
}

export function Counter({ value, decimals = 0, suffix = '' }: { value: number; decimals?: number; suffix?: string }) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduce) { el.textContent = value.toFixed(decimals) + suffix; return; }
    const c = animate(0, value, { duration: 1.1, ease: 'easeOut', onUpdate: (v) => { el.textContent = v.toFixed(decimals) + suffix; } });
    return () => c.stop();
  }, [value, decimals, suffix, reduce]);
  return <span ref={ref}>{value.toFixed(decimals)}{suffix}</span>;
}

const gradients: Record<string, string> = {
  indigo: 'from-indigo to-midnight', aqua: 'from-aqua to-aqua', coral: 'from-coral to-coral', violet: 'from-violet to-midnight', lime: 'from-lime to-lime',
};
export function StatCard({ label, value, hint, tone = 'indigo', suffix = '', icon: Icon, index = 0, onClick }: { label: string; value: number; hint?: string; tone?: string; suffix?: string; icon?: React.ElementType; index?: number; onClick?: () => void }) {
  const dec = Number.isInteger(value) ? 0 : 1;
  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .06, duration: .4 }}>
      <Card hover className="group relative overflow-hidden h-full">
        {onClick && <button type="button" onClick={onClick} aria-label={`View ${label}`} className="absolute inset-0 z-10 rounded-[inherit] cursor-pointer" />}
        <div className={cn('absolute -right-8 -top-8 w-28 h-28 rounded-full bg-gradient-to-br opacity-15 blur-xl', gradients[tone])} />
        <div className="relative flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-mute uppercase tracking-wide">{label}</p>
            <p className="font-num font-extrabold text-[38px] leading-none mt-3 text-ink"><Counter value={value} decimals={dec} suffix={suffix} /></p>
            {hint && <p className="text-[13.5px] text-mute mt-2.5">{hint}</p>}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {Icon && <div className={cn('w-11 h-11 rounded-2xl grid place-items-center text-white bg-gradient-to-br', gradients[tone])}><Icon className="w-5 h-5" /></div>}
            {onClick && <ArrowUpRight aria-hidden="true" className="w-4 h-4 text-mute transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

export function Skeleton({ className }: { className?: string }) { return <div className={cn('skeleton', className)} />; }

export function Empty({ title, text, action }: { title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="relative overflow-hidden rounded-2xl text-center py-14 px-6">
      <AnimatedBackground variant="light" className="opacity-80" />
      <div className="relative">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-white shadow-card grid place-items-center text-violet"><Inbox className="w-6 h-6" /></div>
        <h3 className="mt-4 text-[18px] font-bold">{title}</h3>
        {text && <p className="text-mute mt-1 max-w-md mx-auto">{text}</p>}
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-coral/40 bg-coral/10 p-5 flex items-center gap-3 text-[#9e2f1b]">
      <AlertTriangle className="w-5 h-5 shrink-0" /><span className="flex-1">{message}</span>
      {onRetry && <Button size="sm" variant="secondary" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

/* ------------------------------------------------------------------ forms */
export function Field({ label, error, hint, required, children, className }: { label: string; error?: string; hint?: string; required?: boolean; children: ReactNode; className?: string }) {
  const id = useId();
  const msgId = `${id}-msg`;
  // Associate the label with the real control whenever the child is a single input-like element.
  const single = isValidElement(children) ? (children as ReactElement<any>) : null;
  const direct = !!single && (typeof single.type !== 'string' || ['input', 'select', 'textarea'].includes(single.type as string));
  const control = direct ? cloneElement(single!, { id, 'aria-describedby': error || hint ? msgId : undefined, 'aria-required': required || undefined }) : <div role="group" aria-labelledby={`${id}-l`}>{children}</div>;
  return (
    <div className={className}>
      <label id={`${id}-l`} htmlFor={direct ? id : undefined} className="block text-[13.5px] font-semibold mb-1.5 text-ink">{label}{required && <span className="text-coral"> *</span>}</label>
      {control}
      {error ? <p id={msgId} role="alert" className="text-[13px] text-[#c2412b] mt-1.5">{error}</p> : hint ? <p id={msgId} className="text-[13px] text-mute mt-1.5">{hint}</p> : null}
    </div>
  );
}
export const TextInput = ({ invalid, className, ...p }: React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) =>
  <input {...p} aria-invalid={invalid} className={cn('input', className)} />;
export const TextArea = ({ invalid, className, ...p }: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) =>
  <textarea {...p} aria-invalid={invalid} className={cn('input min-h-[96px] resize-y', className)} />;
export const SelectInput = ({ invalid, className, children, ...p }: React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) =>
  <select {...p} aria-invalid={invalid} className={cn('input appearance-none bg-[url("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%2716%27 height=%2716%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27%23777991%27 stroke-width=%272.4%27%3E%3Cpath d=%27m6 9 6 6 6-6%27/%3E%3C/svg%3E")] bg-no-repeat bg-[right_12px_center] pr-10', className)}>{children}</select>;

/* ------------------------------------------------------------------ overlays */
export function Modal({ open, onClose, title, subtitle, children, footer, width = 'max-w-2xl' }: { open: boolean; onClose: () => void; title: string; subtitle?: string; children: ReactNode; footer?: ReactNode; width?: string }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[80] grid place-items-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-midnight/55 backdrop-blur-sm" onClick={onClose} />
          <motion.div role="dialog" aria-modal="true" aria-label={title}
            initial={{ opacity: 0, y: 30, scale: .97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 20, scale: .97 }}
            transition={{ type: 'spring', damping: 26, stiffness: 320 }}
            className={cn('relative w-full bg-white rounded-3xl shadow-2xl flex flex-col max-h-[92vh]', width)}>
            <div className="flex items-start justify-between gap-4 px-7 pt-6 pb-4 border-b border-line shrink-0">
              <div><h2 className="text-[22px] font-extrabold">{title}</h2>{subtitle && <p className="text-mute text-[14px] mt-0.5">{subtitle}</p>}</div>
              <button onClick={onClose} aria-label="Close" className="p-2 rounded-xl hover:bg-slate-100 text-mute"><X className="w-5 h-5" /></button>
            </div>
            <div className="px-7 py-6 overflow-y-auto min-h-0">{children}</div>
            {footer && <div className="px-7 py-4 border-t border-line flex justify-end gap-3 shrink-0 bg-[#fbfaff] rounded-b-3xl">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[80]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-midnight/45" onClick={onClose} />
          <motion.aside initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl flex flex-col">
            <div className="flex items-center justify-between px-6 py-5 border-b border-line shrink-0">
              <h2 className="text-[20px] font-extrabold">{title}</h2>
              <button onClick={onClose} aria-label="Close" className="p-2 rounded-xl hover:bg-slate-100"><X className="w-5 h-5" /></button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-6">{children}</div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', danger, onConfirm, onClose }: { open: boolean; title: string; message: string; confirmLabel?: string; danger?: boolean; onConfirm: () => Promise<void> | void; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <Modal open={open} onClose={onClose} title={title} width="max-w-md"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button variant={danger ? 'danger' : 'primary'} loading={busy} onClick={async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }}>{confirmLabel}</Button></>}>
      <p className="text-[15px] text-ink/80">{message}</p>
    </Modal>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="flex gap-1 p-1.5 bg-white border border-line rounded-2xl w-fit max-w-full overflow-x-auto" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cn('relative px-4 py-2 rounded-xl text-[14px] font-semibold whitespace-nowrap transition-colors', value === t.id ? 'text-white' : 'text-mute hover:text-ink')}>
          {value === t.id && <motion.span layoutId="tab-pill" className="absolute inset-0 rounded-xl bg-gradient-to-r from-indigo to-violet" transition={{ type: 'spring', damping: 28, stiffness: 380 }} />}
          <span className="relative flex items-center gap-2">{t.label}{t.count != null && t.count > 0 && <span className={cn('text-[11px] px-1.5 rounded-full', value === t.id ? 'bg-white/25' : 'bg-coral/20 text-[#c2412b]')}>{t.count}</span>}</span>
        </button>
      ))}
    </div>
  );
}

export function Progress({ value, tone = 'indigo' }: { value: number; tone?: string }) {
  return (
    <div className="h-2 rounded-full bg-slate-100 overflow-hidden min-w-[90px]">
      <motion.div initial={{ width: 0 }} animate={{ width: `${Math.min(100, value)}%` }} transition={{ duration: .8, ease: 'easeOut' }}
        className={cn('h-full rounded-full bg-gradient-to-r', gradients[tone])} />
    </div>
  );
}

export function downloadBlob(blob: Blob, name: string) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
