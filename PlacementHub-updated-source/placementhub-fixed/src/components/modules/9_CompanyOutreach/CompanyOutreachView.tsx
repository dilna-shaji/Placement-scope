import { Mail, MessageSquareReply, Repeat } from 'lucide-react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { Badge, StatusBadge } from '../../ui/kit';
import { StatsRow, count } from '../shared';
import { fmtDate } from '../../../lib/format';

export default function CompanyOutreachView() {
  const cfg: ResourceConfig = {
    resource: 'outreach', singular: 'Outreach', title: 'Company outreach & communication',
    subtitle: 'Log every conversation with recruiters and never miss a follow-up.', searchPlaceholder: 'Search subject…',
    filters: [{ name: 'status', label: 'Status', options: ['Draft', 'Sent', 'Replied', 'Follow-up', 'Closed'] }, { name: 'channel', label: 'Channel', options: ['Email', 'Call', 'Meeting', 'LinkedIn'] }, { name: 'companyId', label: 'Company', lookup: 'companies' }],
    defaults: { channel: 'Email', status: 'Draft' },
    fields: [
      { name: 'companyId', label: 'Company', type: 'lookup', lookup: 'companies', required: true }, { name: 'channel', label: 'Channel', type: 'select', options: ['Email', 'Call', 'Meeting', 'LinkedIn'] },
      { name: 'subject', label: 'Subject', required: true, span: 2 }, { name: 'status', label: 'Status', type: 'select', options: ['Draft', 'Sent', 'Replied', 'Follow-up', 'Closed'] },
      { name: 'nextFollowupDate', label: 'Next follow-up', type: 'date' }, { name: 'message', label: 'Message / notes', type: 'textarea' },
    ],
    columns: [
      { key: 'subject', label: 'Subject', render: (r) => <div><p className="font-semibold">{r.subject}</p><p className="text-[13px] text-mute">{r.companyName}</p></div> },
      { key: 'channel', label: 'Channel', render: (r) => <Badge tone="indigo">{r.channel}</Badge> },
      { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
      { key: 'nextFollowupDate', label: 'Follow-up', render: (r) => fmtDate(r.nextFollowupDate) },
      { key: 'createdAt', label: 'Logged', render: (r) => fmtDate(r.createdAt) },
    ],
    topSlot: (items) => <StatsRow stats={[
      { label: 'Conversations', value: items.length, icon: Mail, tone: 'indigo' },
      { label: 'Replied', value: count(items, (o) => o.status === 'Replied'), icon: MessageSquareReply, tone: 'aqua' },
      { label: 'Follow-ups due', value: count(items, (o) => o.status === 'Follow-up'), icon: Repeat, tone: 'coral' },
      { label: 'Drafts', value: count(items, (o) => o.status === 'Draft'), tone: 'violet' }]} />,
  };
  return <ResourcePage cfg={cfg} />;
}
