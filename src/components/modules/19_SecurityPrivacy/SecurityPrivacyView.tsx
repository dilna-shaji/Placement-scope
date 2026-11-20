import { KeyRound, LogOut, ShieldAlert, ShieldCheck, Timer, Unlock, Users } from 'lucide-react';
import { api, ApiError } from '../../../lib/api';
import { useUI } from '../../../context/UIContext';
import { Badge, Button, Card, ErrorNote, PageHeader, Skeleton, StatCard, useFetch } from '../../ui/kit';
import { fmtDateTime } from '../../../lib/format';
import type { Row } from '../../../types';

export default function SecurityPrivacyView() {
  const { toast } = useUI();
  const { data, loading, error, reload } = useFetch<{ sessions: Row[]; failedAttempts: Row[]; lockedUsers: Row[]; resets: Row[]; policy: Record<string, number> }>('/api/security/overview');
  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast(ok); reload(); } catch (e) { toast((e as ApiError).message, 'error'); } };
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  return (
    <div className="space-y-7">
      <PageHeader title="Security & privacy" subtitle="Live sessions, failed sign-ins, locked accounts and the active policy." actions={<Button variant="secondary" onClick={reload}>Refresh</Button>} />
      {loading || !data ? <div className="grid xl:grid-cols-4 gap-5">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-36" />)}</div> : <>
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-5">
          <StatCard index={0} label="Live sessions" value={data.sessions.length} icon={Users} tone="indigo" />
          <StatCard index={1} label="Failed sign-ins (24h)" value={data.failedAttempts.length} icon={ShieldAlert} tone="coral" />
          <StatCard index={2} label="Locked accounts" value={data.lockedUsers.length} icon={Unlock} tone="violet" />
          <StatCard index={3} label="Reset requests" value={data.resets.length} icon={KeyRound} tone="aqua" hint="recent" />
        </div>
        <Card><h3 className="font-bold text-[17px] mb-4 flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-aqua" />Active policy <span className="text-[13px] font-normal text-mute">(edit in System Settings)</span></h3>
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">{[['Lock after', `${data.policy.max_failed_logins} failures`], ['Base lockout', `${data.policy.lockout_minutes} min (doubles each repeat)`], ['Idle timeout', `${data.policy.session_idle_minutes} min`], ['Min. password length', `${data.policy.password_min_length}`]].map(([k, v]) => <div key={k} className="rounded-xl bg-canvas p-4"><p className="text-[12px] uppercase font-semibold text-mute">{k}</p><p className="font-bold text-[16px] mt-1">{v}</p></div>)}</div>
          <p className="text-[13.5px] text-mute mt-4">Passwords are hashed with Argon2id. Sessions use HttpOnly cookies with CSRF tokens. Role and department scope are enforced on every API call.</p></Card>
        <div className="grid xl:grid-cols-2 gap-6">
          <Card padded={false} className="overflow-hidden"><div className="p-5 border-b border-line"><h3 className="font-bold text-[17px]">Active sessions</h3></div><div className="overflow-x-auto"><table className="tbl w-full min-w-[480px]"><thead><tr><th>User</th><th>IP</th><th>Last seen</th><th /></tr></thead><tbody>
            {data.sessions.map((s) => <tr key={s.id}><td><p className="font-semibold">{s.userName}</p><p className="text-[12.5px] text-mute">{s.role}</p></td><td className="font-mono text-[12.5px]">{s.ip}</td><td className="text-mute">{fmtDateTime(s.lastSeenAt)}</td><td className="text-right">{s.current ? <Badge tone="aqua">This session</Badge> : <Button size="sm" variant="danger" onClick={() => run(() => api.post(`/api/security/sessions/${s.id}/revoke`), 'Session revoked')}><LogOut className="w-3.5 h-3.5" />Revoke</Button>}</td></tr>)}</tbody></table></div></Card>
          <Card padded={false} className="overflow-hidden"><div className="p-5 border-b border-line"><h3 className="font-bold text-[17px]">Locked accounts</h3></div>
            {!data.lockedUsers.length ? <p className="p-8 text-center text-mute">No accounts are locked.</p> : <ul className="divide-y divide-line">{data.lockedUsers.map((u) => <li key={u.id} className="p-4 flex items-center justify-between gap-3"><div><p className="font-semibold">{u.fullName}</p><p className="text-[13px] text-mute">Locked until {fmtDateTime(u.lockedUntil)}</p></div><Button size="sm" variant="success" onClick={() => run(() => api.post(`/api/users/${u.id}/unlock`), 'Account unlocked')}><Unlock className="w-3.5 h-3.5" />Unlock</Button></li>)}</ul>}</Card>
        </div>
        <Card padded={false} className="overflow-hidden"><div className="p-5 border-b border-line"><h3 className="font-bold text-[17px] flex items-center gap-2"><Timer className="w-5 h-5 text-coral" />Failed sign-in attempts (24h)</h3></div><div className="overflow-x-auto max-h-[360px]"><table className="tbl w-full min-w-[560px]"><thead><tr><th>Time</th><th>Identifier</th><th>IP</th><th>Reason</th></tr></thead><tbody>
          {data.failedAttempts.map((a) => <tr key={a.id}><td className="text-mute whitespace-nowrap">{fmtDateTime(a.createdAt)}</td><td>{a.identifier || '—'}</td><td className="font-mono text-[12.5px]">{a.ipAddress}</td><td><Badge tone="coral">{a.reason}</Badge></td></tr>)}</tbody></table>{!data.failedAttempts.length && <p className="p-8 text-center text-mute">No failed attempts in the last 24 hours.</p>}</div></Card>
      </>}
    </div>
  );
}
