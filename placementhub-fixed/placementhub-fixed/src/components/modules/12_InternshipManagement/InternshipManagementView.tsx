import { Clock, CheckCircle2, Award } from 'lucide-react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { Progress, StatusBadge, Badge } from '../../ui/kit';
import { StatsRow, count } from '../shared';
import { fmtDate } from '../../../lib/format';

export default function InternshipManagementView() {
  const cfg: ResourceConfig = {
    resource: 'internships', singular: 'Internship', title: 'Internship management', subtitle: 'Track progress, mentors, evaluations and PPO conversions.',
    searchPlaceholder: 'Search company…', filters: [{ name: 'status', label: 'Status', options: ['Ongoing', 'Completed', 'PPO Converted', 'Terminated'] }],
    defaults: { status: 'Ongoing', progressPercent: 0, durationMonths: 2, ppoOffered: false },
    fields: [
      { name: 'studentId', label: 'Student', type: 'lookup', lookup: 'students', required: true, createOnly: true }, { name: 'companyName', label: 'Company', required: true },
      { name: 'stipendPerMonth', label: 'Stipend / month (₹)', type: 'number' }, { name: 'durationMonths', label: 'Duration (months)', type: 'number' },
      { name: 'startDate', label: 'Start date', type: 'date' }, { name: 'endDate', label: 'End date', type: 'date' },
      { name: 'mentorName', label: 'Mentor' }, { name: 'mentorEmail', label: 'Mentor e-mail', type: 'email' },
      { name: 'progressPercent', label: 'Progress %', type: 'number' }, { name: 'status', label: 'Status', type: 'select', options: ['Ongoing', 'Completed', 'PPO Converted', 'Terminated'] },
      { name: 'evaluationGrade', label: 'Evaluation grade' }, { name: 'ppoCtcLpa', label: 'PPO CTC (LPA)', type: 'number', step: '0.1' },
      { name: 'ppoOffered', label: 'PPO', type: 'checkbox', hint: 'Pre-placement offer extended' },
    ],
    columns: [
      { key: 'studentName', label: 'Student', render: (r) => <div><p className="font-semibold">{r.studentName}</p><p className="text-[13px] text-mute">{r.rollNo} · {r.departmentCode}</p></div> },
      { key: 'companyName', label: 'Company' }, { key: 'dates', label: 'Period', render: (r) => `${fmtDate(r.startDate)} – ${fmtDate(r.endDate)}` },
      { key: 'progressPercent', label: 'Progress', render: (r) => <div className="flex items-center gap-3"><Progress value={r.progressPercent} tone="aqua" /><span className="font-num font-bold text-[13px]">{r.progressPercent}%</span></div>, sort: (r) => r.progressPercent },
      { key: 'ppoOffered', label: 'PPO', render: (r) => r.ppoOffered ? <Badge tone="lime">{r.ppoCtcLpa ? `${r.ppoCtcLpa} LPA` : 'Offered'}</Badge> : '—' },
      { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
    ],
    topSlot: (items) => <StatsRow stats={[
      { label: 'Internships', value: items.length, icon: Clock, tone: 'indigo' }, { label: 'Ongoing', value: count(items, (i) => i.status === 'Ongoing'), tone: 'violet' },
      { label: 'Completed', value: count(items, (i) => i.status === 'Completed'), icon: CheckCircle2, tone: 'aqua' }, { label: 'PPO offered', value: count(items, (i) => i.ppoOffered), icon: Award, tone: 'coral' }]} />,
  };
  return <ResourcePage cfg={cfg} />;
}
