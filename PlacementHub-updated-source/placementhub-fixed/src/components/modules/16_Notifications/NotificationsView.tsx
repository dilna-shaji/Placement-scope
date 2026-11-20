import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Bell, CheckCheck, Megaphone, Send, Trash2 } from 'lucide-react';
import { api, ApiError } from '../../../lib/api';
import { useAuth } from '../../../context/AuthContext';
import { useUI } from '../../../context/UIContext';
import { Button, Card, Empty, ErrorNote, Field, Modal, PageHeader, SelectInput, TextArea, TextInput, useFetch } from '../../ui/kit';
import { cn, fmtDateTime } from '../../../lib/format';
import type { Row } from '../../../types';

export default function NotificationsView() {
  const { can, lookups } = useAuth();
  const { toast } = useUI();
  const { data, loading, error, reload } = useFetch<{ items: Row[]; unread: number }>('/api/notifications');
  const [compose, setCompose] = useState(false); const [f, setF] = useState<Row>({ audience: '', type: 'system' }); const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const ping = () => window.dispatchEvent(new Event('ph:notifications'));
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); reload(); ping(); } catch (e) { toast((e as ApiError).message, 'error'); } };
  const send = async () => {
    setBusy(true); setErr('');
    try { const r = await api.post<{ recipients: number }>('/api/notifications', f); toast(`Sent to ${r.recipients} recipient(s)`); setCompose(false); setF({ audience: '', type: 'system' }); }
    catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-7">
      <PageHeader title="Notifications & reminders" subtitle={`${data?.unread ?? 0} unread`} actions={<>
        {!!data?.unread && <Button variant="secondary" onClick={() => act(() => api.post('/api/notifications/read-all'))}><CheckCheck className="w-4 h-4" />Mark all read</Button>}
        {can('notifications:send') && <Button onClick={() => setCompose(true)}><Megaphone className="w-4 h-4" />New announcement</Button>}</>} />
      {error ? <ErrorNote message={error} onRetry={reload} /> : !loading && !data?.items.length ? <Empty title="You’re all caught up" text="Approvals, drive updates and announcements will appear here." /> : (
        <div className="space-y-3 max-w-4xl">
          <AnimatePresence initial={false}>{data?.items.map((n) => (
            <motion.div key={n.id} layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 50 }}>
              <Card className={cn('!p-5 flex gap-4 items-start', !n.read && 'border-violet/50 bg-violet/[.04]')}>
                <div className={cn('w-11 h-11 rounded-2xl grid place-items-center shrink-0', n.read ? 'bg-slate-100 text-mute' : 'bg-gradient-to-br from-indigo to-violet text-white')}><Bell className="w-5 h-5" /></div>
                <div className="flex-1 min-w-0"><p className="font-bold text-[16px]">{n.title}</p>{n.message && <p className="text-[14.5px] text-ink/75 mt-0.5 whitespace-pre-line">{n.message}</p>}<p className="text-[12.5px] text-mute mt-1.5">{fmtDateTime(n.createdAt)}</p></div>
                <div className="flex gap-1">{!n.read && <Button size="sm" variant="ghost" onClick={() => act(() => api.post(`/api/notifications/${n.id}/read`))}>Mark read</Button>}<button aria-label="Delete" onClick={() => act(() => api.del(`/api/notifications/${n.id}`))} className="p-2 rounded-lg text-mute hover:bg-coral/15 hover:text-[#c2412b]"><Trash2 className="w-4 h-4" /></button></div>
              </Card></motion.div>))}</AnimatePresence></div>)}
      <Modal open={compose} onClose={() => setCompose(false)} title="New announcement" width="max-w-xl" footer={<><Button variant="secondary" onClick={() => setCompose(false)}>Cancel</Button><Button loading={busy} onClick={send}><Send className="w-4 h-4" />Send</Button></>}>
        {err && <div role="alert" className="mb-4 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{err}</div>}
        <div className="space-y-5">
          <Field label="Audience" required><SelectInput value={f.audience} onChange={(e) => setF({ ...f, audience: e.target.value })}><option value="">Select…</option><option value="all">Everyone</option>
            <optgroup label="By role"><option value="role:department_tpo">Department TPOs</option><option value="role:corporate_recruiter">Corporate recruiters</option><option value="role:student_coordinator">Student coordinators</option></optgroup>
            <optgroup label="By department">{lookups.departments?.map((d) => <option key={d.id} value={`department:${d.id}`}>{d.label}</option>)}</optgroup></SelectInput></Field>
          <Field label="Type"><SelectInput value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="system">General</option><option value="drive">Drive</option><option value="approval">Approval</option><option value="offer">Offer</option></SelectInput></Field>
          <Field label="Title" required><TextInput value={f.title || ''} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Message"><TextArea value={f.message || ''} onChange={(e) => setF({ ...f, message: e.target.value })} /></Field>
        </div>
      </Modal>
    </div>
  );
}
