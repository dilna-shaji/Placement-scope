import { Building2, FileCheck2, Users } from 'lucide-react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { Badge, StatusBadge } from '../../ui/kit';
import { useAuth } from '../../../context/AuthContext';
import { StatsRow, TIERS, count } from '../shared';
import { fmtDate } from '../../../lib/format';

export default function CompanyManagementView() {
  const { user } = useAuth();
  const rec = user!.role === 'corporate_recruiter';
  const cfg: ResourceConfig = {
    resource: 'companies', singular: 'Company', title: rec ? 'Company profile' : 'Company directory',
    subtitle: rec ? 'Keep your company details current. Tier and MoU status are managed by the placement cell.' : 'Recruiters, tiers and MoU status.',
    searchPlaceholder: 'Search company, industry or location…',
    filters: rec ? [] : [{ name: 'tier', label: 'Tier', options: TIERS }, { name: 'mouStatus', label: 'MoU', options: ['Signed', 'In Discussion', 'Pending Renewal', 'None'] }],
    defaults: { tier: 'Core Corporate', mouStatus: 'None' },
    canCreate: () => !rec,
    fields: [
      { name: 'name', label: 'Company name', required: true, hideFor: () => rec }, { name: 'industry', label: 'Industry' },
      { name: 'tier', label: 'Tier', type: 'select', options: TIERS, hideFor: () => rec }, { name: 'mouStatus', label: 'MoU status', type: 'select', options: ['None', 'In Discussion', 'Signed', 'Pending Renewal'], hideFor: () => rec },
      { name: 'location', label: 'Headquarters / location' }, { name: 'website', label: 'Website' },
      { name: 'contactName', label: 'Primary contact' }, { name: 'contactDesignation', label: 'Contact designation' },
      { name: 'contactEmail', label: 'Contact e-mail', type: 'email' }, { name: 'contactPhone', label: 'Contact phone' },
      { name: 'lastDriveDate', label: 'Last drive date', type: 'date', hideFor: () => rec }, { name: 'about', label: 'About the company', type: 'textarea' },
    ],
    columns: [
      { key: 'name', label: 'Company', render: (r) => <div><p className="font-semibold">{r.name}</p><p className="text-[13px] text-mute">{r.industry || '—'} · {r.location || '—'}</p></div> },
      { key: 'tier', label: 'Tier', render: (r) => <Badge tone={r.tier.startsWith('Super') ? 'coral' : r.tier.startsWith('Dream') ? 'violet' : 'slate'}>{r.tier}</Badge> },
      { key: 'contactName', label: 'Contact', render: (r) => <div><p>{r.contactName || '—'}</p><p className="text-[13px] text-mute">{r.contactEmail}</p></div> },
      { key: 'mouStatus', label: 'MoU', render: (r) => <StatusBadge value={r.mouStatus} /> },
      { key: 'lastDriveDate', label: 'Last drive', render: (r) => fmtDate(r.lastDriveDate) },
    ],
    topSlot: rec ? undefined : (items) => <StatsRow stats={[
      { label: 'Companies', value: items.length, icon: Building2, tone: 'indigo' },
      { label: 'MoU signed', value: count(items, (c) => c.mouStatus === 'Signed'), icon: FileCheck2, tone: 'aqua' },
      { label: 'In discussion', value: count(items, (c) => c.mouStatus === 'In Discussion'), icon: Users, tone: 'violet' },
      { label: 'Super dream / dream', value: count(items, (c) => c.tier.startsWith('Super') || c.tier.startsWith('Dream')), tone: 'coral' }]} />,
  };
  return <ResourcePage cfg={cfg} />;
}
