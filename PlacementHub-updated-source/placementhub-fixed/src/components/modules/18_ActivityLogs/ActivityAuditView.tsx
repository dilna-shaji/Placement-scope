import { useState } from 'react';
import { Download, Search } from 'lucide-react';
import { Button, Card, ErrorNote, PageHeader, SelectInput, StatusBadge, TextInput, useFetch, Empty, downloadBlob } from '../../ui/kit';
import { qs } from '../../../lib/api';
import { fmtDateTime } from '../../../lib/format';
import type { Page } from '../../../types';

export default function ActivityAuditView() {
  const [q, setQ] = useState(''); const [status, setStatus] = useState(''); const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useFetch<Page>(`/api/audit${qs({ q, status, page, pageSize: 40 })}`);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;
  const exp = async () => { const r = await fetch('/api/reports/export?dataset=audit&format=csv', { credentials: 'same-origin' }); if (r.ok) downloadBlob(await r.blob(), 'audit_log.csv'); };
  return (
    <div className="space-y-7">
      <PageHeader title="Activity logs & audit" subtitle="An append-only record of sign-ins, role changes, approvals, exports and denied requests." actions={<Button variant="secondary" onClick={exp}><Download className="w-4 h-4" />Export CSV</Button>} />
      <Card padded={false} className="overflow-hidden">
        <div className="p-5 flex flex-wrap gap-3 border-b border-line">
          <div className="relative flex-1 min-w-[220px] max-w-md"><Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-mute" /><TextInput className="pl-10" placeholder="Search actor, action or details…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>
          <SelectInput className="w-auto min-w-[150px]" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All outcomes</option><option>Success</option><option>Warning</option><option>Failed</option></SelectInput>
          <span className="ml-auto self-center text-[13.5px] text-mute">{data?.total ?? 0} events</span>
        </div>
        {error ? <div className="p-6"><ErrorNote message={error} onRetry={reload} /></div> : !data?.items.length && !loading ? <Empty title="No audit events" /> : (
          <div className="overflow-x-auto"><table className="tbl w-full min-w-[860px]"><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Details</th><th>IP</th><th>Outcome</th></tr></thead>
            <tbody>{data?.items.map((l) => <tr key={l.id}><td className="whitespace-nowrap text-mute">{fmtDateTime(l.createdAt)}</td><td><p className="font-semibold">{l.actorName}</p><p className="text-[12.5px] text-mute">{l.actorRole || '—'}</p></td><td>{l.action}</td><td className="text-mute">{l.entityType} {l.entityId}</td><td className="max-w-[320px] truncate" title={l.details}>{l.details}</td><td className="font-mono text-[12.5px]">{l.ipAddress}</td><td><StatusBadge value={l.status} /></td></tr>)}</tbody></table></div>)}
        <div className="flex items-center justify-between px-5 py-3.5 border-t border-line text-[14px] text-mute"><span>Page {page} of {pages}</span>
          <div className="flex gap-2"><Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button><Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button></div></div>
      </Card>
    </div>
  );
}
