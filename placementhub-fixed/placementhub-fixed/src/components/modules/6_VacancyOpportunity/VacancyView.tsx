import { Briefcase, CheckCircle2, Hourglass, Send } from 'lucide-react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { Badge, Button, StatusBadge } from '../../ui/kit';
import { useAuth } from '../../../context/AuthContext';
import { useUI } from '../../../context/UIContext';
import { api, ApiError } from '../../../lib/api';
import { StatsRow, count } from '../shared';
import { fmtDate } from '../../../lib/format';

export default function VacancyView() {
  const { user, can } = useAuth();
  const { toast } = useUI();
  const rec = user!.role === 'corporate_recruiter';
  const cfg: ResourceConfig = {
    resource: 'vacancies', singular: 'Vacancy', title: rec ? 'My vacancies' : 'Vacancies & opportunities',
    subtitle: rec ? 'Create a vacancy, then submit it for verification. Approved vacancies become visible to eligible students.' : 'Job notification forms with eligibility criteria.',
    searchPlaceholder: 'Search vacancy title…',
    filters: [{ name: 'status', label: 'Status', options: ['Draft', 'Pending Verification', 'Approved', 'Active', 'Closed', 'Archived'] }, { name: 'jobType', label: 'Type', options: ['Full-Time', 'Internship + PPO', 'Internship Only'] }],
    defaults: { jobType: 'Full-Time', status: 'Draft', openings: 1, minCgpa: 6, maxBacklogs: 0, eligibleDepartments: [], locations: [] },
    fields: [
      { name: 'title', label: 'Job title', required: true },
      { name: 'companyId', label: 'Company', type: 'lookup', lookup: 'companies', required: true, hideFor: () => rec, createOnly: false },
      { name: 'jobType', label: 'Type', type: 'select', options: ['Full-Time', 'Internship + PPO', 'Internship Only'] },
      { name: 'ctcLpa', label: 'CTC (LPA)', type: 'number', step: '0.1' }, { name: 'stipendPerMonth', label: 'Stipend / month (₹)', type: 'number' },
      { name: 'openings', label: 'Openings', type: 'number' }, { name: 'minCgpa', label: 'Minimum CGPA', type: 'number', step: '0.1' },
      { name: 'maxBacklogs', label: 'Max active backlogs', type: 'number' },
      { name: 'applicationDeadline', label: 'Application deadline', type: 'date' }, { name: 'driveDate', label: 'Drive date', type: 'date' },
      { name: 'eligibleDepartments', label: 'Eligible departments', type: 'multi', lookup: 'departments' },
      { name: 'locations', label: 'Locations', type: 'tags', placeholder: 'Pune, Mumbai' },
      { name: 'status', label: 'Status', type: 'select', options: rec ? ['Draft', 'Pending Verification'] : ['Draft', 'Pending Verification', 'Approved', 'Active', 'Closed', 'Archived'], hideFor: () => rec && false },
      { name: 'description', label: 'Description', type: 'textarea' },
    ],
    columns: [
      { key: 'title', label: 'Vacancy', render: (r) => <div><p className="font-semibold">{r.title}</p><p className="text-[13px] text-mute">{r.companyName} · {r.jobType}</p></div> },
      { key: 'ctcLpa', label: 'CTC', render: (r) => <span className="font-num font-bold">{r.ctcLpa} LPA</span>, sort: (r) => r.ctcLpa },
      { key: 'eligibleDepartments', label: 'Eligible', render: (r) => <div className="flex gap-1 flex-wrap">{(r.eligibleDepartments || []).map((d: string) => <Badge key={d} tone="violet">{d}</Badge>)}</div> },
      { key: 'applicationDeadline', label: 'Deadline', render: (r) => fmtDate(r.applicationDeadline) },
      { key: 'applicationsCount', label: 'Applicants', render: (r) => `${r.applicationsCount} (${r.shortlistedCount} shortlisted)` },
      { key: 'status', label: 'Status', render: (r) => <StatusBadge value={r.status} /> },
    ],
    rowActions: (r, reload) => {
      if (user?.role === 'student') {
        if (r.hasApplied) {
          return <Badge tone="aqua">Applied</Badge>;
        }
        if (r.isEligible) {
          return (
            <Button
              size="sm"
              variant="primary"
              onClick={async () => {
                try {
                  await api.post('/api/student/apply', { vacancyId: r.id });
                  toast(`Successfully applied for ${r.title}!`);
                  reload();
                } catch (e) {
                  toast((e as ApiError).message, 'error');
                }
              }}
            >
              Apply
            </Button>
          );
        }
        return <Badge tone="slate">Not Eligible</Badge>;
      }
      return r.status === 'Draft' && can('vacancies:write') ? (
        <Button size="sm" variant="success" onClick={async () => { try { await api.post(`/api/vacancies/${r.id}/submit`); toast('Submitted for verification'); reload(); } catch (e) { toast((e as ApiError).message, 'error'); } }}><Send className="w-3.5 h-3.5" />Submit</Button>
      ) : null;
    },
    canEditRow: (r, u) => u.role !== 'corporate_recruiter' || ['Draft', 'Pending Verification', 'Approved', 'Active'].includes(r.status),
    topSlot: (items) => <StatsRow stats={[
      { label: 'Vacancies', value: items.length, icon: Briefcase, tone: 'indigo' },
      { label: 'Open now', value: count(items, (v) => ['Approved', 'Active'].includes(v.status)), icon: CheckCircle2, tone: 'aqua' },
      { label: 'Awaiting verification', value: count(items, (v) => v.status === 'Pending Verification'), icon: Hourglass, tone: 'coral' },
      { label: 'Drafts', value: count(items, (v) => v.status === 'Draft'), icon: Send, tone: 'violet' }]} />,
  };
  return <ResourcePage cfg={cfg} />;
}
