import { Award, BadgeCheck, TrendingUp, Trophy } from 'lucide-react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { Badge, StatusBadge } from '../../ui/kit';
import { StatsRow, count } from '../shared';
import { fmtDate } from '../../../lib/format';

export default function PlacementManagementView() {
  const cfg: ResourceConfig = {
    resource: 'placements', singular: 'Offer', title: 'Placement management', subtitle: 'Offers, packages and verification. Saving an accepted offer marks the student as Placed.',
    searchPlaceholder: 'Search designation, offer ref or location…', filters: [{ name: 'companyId', label: 'Company', lookup: 'companies' }],
    defaults: { offerAccepted: false, verified: false },
    fields: [
      { name: 'studentId', label: 'Student', type: 'lookup', lookup: 'students', required: true, createOnly: true }, { name: 'companyId', label: 'Company', type: 'lookup', lookup: 'companies', required: true },
      { name: 'designation', label: 'Designation', required: true }, { name: 'location', label: 'Location' },
      { name: 'ctcLpa', label: 'CTC (LPA)', type: 'number', step: '0.1', required: true }, { name: 'baseLpa', label: 'Base (LPA)', type: 'number', step: '0.1' },
      { name: 'signedDate', label: 'Offer date', type: 'date' }, { name: 'joiningDate', label: 'Joining date', type: 'date' },
      { name: 'offerAccepted', label: 'Accepted', type: 'checkbox', hint: 'Student accepted this offer' }, { name: 'verified', label: 'Verified', type: 'checkbox', hint: 'Verified by the placement cell' },
    ],
    columns: [
      { key: 'studentName', label: 'Student', render: (r) => <div><p className="font-semibold">{r.studentName}</p><p className="text-[13px] text-mute">{r.rollNo} · {r.departmentCode}</p></div> },
      { key: 'companyName', label: 'Company', render: (r) => <div><p>{r.companyName}</p><p className="text-[13px] text-mute">{r.designation}</p></div> },
      { key: 'ctcLpa', label: 'CTC', render: (r) => <span className="font-num font-extrabold text-[16px]">{r.ctcLpa} LPA</span>, sort: (r) => r.ctcLpa },
      { key: 'offerRef', label: 'Ref', render: (r) => <span className="font-mono text-[13px]">{r.offerRef}</span> }, { key: 'signedDate', label: 'Offer date', render: (r) => fmtDate(r.signedDate) },
      { key: 'offerAccepted', label: 'Status', render: (r) => <div className="flex gap-1.5 flex-wrap"><StatusBadge value={r.offerAccepted ? 'Placed' : 'Pending'} />{r.verified && <Badge tone="lime">Verified</Badge>}</div> },
    ],
    topSlot: (items) => {
      const acc = items.filter((o) => o.offerAccepted);
      return <StatsRow stats={[
        { label: 'Offers', value: items.length, icon: Award, tone: 'indigo' }, { label: 'Accepted', value: acc.length, icon: BadgeCheck, tone: 'aqua' },
        { label: 'Average CTC (LPA)', value: acc.length ? +(acc.reduce((a, o) => a + o.ctcLpa, 0) / acc.length).toFixed(2) : 0, icon: TrendingUp, tone: 'violet' },
        { label: 'Highest CTC (LPA)', value: acc.reduce((m, o) => Math.max(m, o.ctcLpa), 0), icon: Trophy, tone: 'coral' }]} />;
    },
  };
  void count;
  return <ResourcePage cfg={cfg} />;
}
