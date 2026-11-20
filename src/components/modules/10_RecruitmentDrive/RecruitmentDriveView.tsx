import { CalendarDays, Radio, CheckCircle2, Users } from 'lucide-react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { Badge, StatusBadge } from '../../ui/kit';
import { StatsRow, count } from '../shared';
import { fmtDate } from '../../../lib/format';
import { useAuth } from '../../../context/AuthContext';

const ROUNDS = ['Pre-Placement Talk', 'Online Aptitude Test', 'Technical Round 1', 'Technical Round 2', 'Group Discussion', 'HR Interview', 'Final Offers'];

export default function RecruitmentDriveView() {
  const { lookups } = useAuth();
  const cfg: ResourceConfig = {
    resource: 'drives', singular: 'Drive', title: 'Recruitment drives', subtitle: 'Schedule campus drives and monitor each round.',
    searchPlaceholder: 'Search drive or venue…',
    filters: [{ name: 'status', label: 'Status', options: [{ value: 'Upcoming,Live Today', label: 'Upcoming + live' }, 'Upcoming', 'Live Today', 'Completed', 'Postponed'] }, { name: 'mode', label: 'Mode', options: ['On-Campus', 'Virtual', 'Hybrid'] }],
    defaults: { mode: 'On-Campus', stage: ROUNDS[0], status: 'Upcoming', registeredCount: 0, shortlistedCount: 0, selectedCount: 0 },
    fields: [
      { name: 'title', label: 'Drive title', required: true, span: 2 }, { name: 'companyId', label: 'Company', type: 'lookup', lookup: 'companies', required: true },
      { name: 'vacancyId', label: 'Linked vacancy (same company)', type: 'select', options: (lookups.vacancies || []).map((v) => ({ value: v.id, label: v.label })), hint: 'Optional' },
      { name: 'date', label: 'Date', type: 'date', required: true }, { name: 'mode', label: 'Mode', type: 'select', options: ['On-Campus', 'Virtual', 'Hybrid'] },
      { name: 'venue', label: 'Venue / link' }, { name: 'stage', label: 'Current round', type: 'select', options: ROUNDS },
      { name: 'status', label: 'Status', type: 'select', options: ['Upcoming', 'Live Today', 'Completed', 'Postponed'] },
      { name: 'registeredCount', label: 'Registered', type: 'number' }, { name: 'shortlistedCount', label: 'Shortlisted', type: 'number' }, { name: 'selectedCount', label: 'Selected', type: 'number' },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ],
    columns: [
      { key: 'title', label: 'Drive', render: (r) => <div><p className="font-semibold">{r.title}</p><p className="text-[13px] text-mute">{r.companyName}</p></div> },
      { key: 'date', label: 'Date', render: (r) => fmtDate(r.date) }, { key: 'mode', label: 'Mode', render: (r) => <Badge tone="indigo">{r.mode}</Badge> },
      { key: 'stage', label: 'Round' },
      { key: 'funnel', label: 'Reg → Short → Sel', render: (r) => <span className="font-num font-bold">{r.registeredCount} → {r.shortlistedCount} → {r.selectedCount}</span> },
      { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
    ],
    topSlot: (items) => <StatsRow stats={[
      { label: 'Drives', value: items.length, icon: CalendarDays, tone: 'indigo' },
      { label: 'Upcoming / live', value: count(items, (d) => ['Upcoming', 'Live Today'].includes(d.status)), icon: Radio, tone: 'coral' },
      { label: 'Completed', value: count(items, (d) => d.status === 'Completed'), icon: CheckCircle2, tone: 'aqua' },
      { label: 'Total selected', value: items.reduce((a, d) => a + (d.selectedCount || 0), 0), icon: Users, tone: 'violet' }]} />,
  };
  return <ResourcePage cfg={cfg} />;
}
