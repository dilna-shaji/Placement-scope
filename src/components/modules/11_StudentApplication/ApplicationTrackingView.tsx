import { useState } from 'react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { SelectInput, StatusBadge, Card } from '../../ui/kit';
import { StatsRow, STAGES, count } from '../shared';
import { api, ApiError } from '../../../lib/api';
import { useAuth } from '../../../context/AuthContext';
import { useUI } from '../../../context/UIContext';
import { Target, Sparkles, CheckCircle2, XCircle } from 'lucide-react';
import type { Row } from '../../../types';

function StageSelect({ row, onDone }: { row: Row; onDone: () => void }) {
  const { toast } = useUI();
  const [busy, setBusy] = useState(false);
  return (
    <SelectInput disabled={busy} className="!py-1.5 !text-[13px] !w-[130px]" value={row.stage} aria-label="Update stage"
      onChange={async (e) => { setBusy(true); try { await api.put(`/api/applications/${row.id}`, { stage: e.target.value }); toast(`Stage updated to ${e.target.value}`); onDone(); } catch (x) { toast((x as ApiError).message, 'error'); } finally { setBusy(false); } }}>
      {STAGES.map((s) => <option key={s}>{s}</option>)}
    </SelectInput>
  );
}

export default function ApplicationTrackingView() {
  const { user, can } = useAuth();
  const { toast } = useUI();
  const [k, setK] = useState(0);
  const rec = user!.role === 'corporate_recruiter';
  const cfg: ResourceConfig = {
    resource: 'applications', singular: 'Application', title: rec ? 'Applications received' : 'Application & selection tracking',
    subtitle: rec ? 'Candidates shared with your company. Move them through your selection stages.' : 'Eligibility is checked by the server when an application is created.',
    noSearch: true, filters: [{ name: 'stage', label: 'Stage', options: [
      { value: 'Shortlisted,Aptitude,Technical,HR', label: 'Shortlisted + interviews' },
      { value: 'Applied,Shortlisted,Aptitude,Technical,HR', label: 'In progress' },
      ...STAGES,
    ] }],
    defaults: { stage: 'Applied' }, canCreate: () => !rec && user?.role !== 'student',
    fields: [
      { name: 'studentId', label: 'Student', type: 'lookup', lookup: 'students', required: true, createOnly: true },
      { name: 'vacancyId', label: 'Vacancy', type: 'lookup', lookup: 'vacancies', required: true, createOnly: true },
      { name: 'stage', label: 'Stage', type: 'select', options: STAGES }, { name: 'score', label: 'Score (0–100)', type: 'number' },
      { name: 'remarks', label: 'Remarks', type: 'textarea' },
    ],
    columns: [
      { key: 'studentName', label: 'Candidate', render: (r) => <div><p className="font-semibold">{r.studentName}</p><p className="text-[13px] text-mute">{r.rollNo} · {r.departmentCode} · CGPA {r.cgpa}</p></div> },
      { key: 'vacancyTitle', label: 'Vacancy', render: (r) => <div><p>{r.vacancyTitle}</p><p className="text-[13px] text-mute">{r.companyName}</p></div> },
      { key: 'stage', label: 'Stage', render: (r) => <StatusBadge value={r.stage} /> }, { key: 'score', label: 'Score', render: (r) => r.score ?? '—' },
      ...(user?.role === 'student' ? [] : can('applications:write') ? [{ key: 'move', label: 'Move to', render: (r: Row) => <StageSelect row={r} onDone={() => setK((x) => x + 1)} /> }] : []),
    ],
    rowActions: (r, reload) => {
      if (user?.role === 'student' && ['Applied', 'Shortlisted', 'Aptitude', 'Technical', 'HR'].includes(r.stage)) {
        return (
          <button
            onClick={async () => {
              if (window.confirm(`Withdraw application for ${r.vacancyTitle}?`)) {
                try {
                  await api.post(`/api/student/withdraw/${r.id}`);
                  toast('Application withdrawn');
                  reload();
                } catch (e) {
                  toast((e as ApiError).message, 'error');
                }
              }
            }}
            className="text-[12px] font-semibold text-coral hover:underline px-2 py-1"
          >
            Withdraw
          </button>
        );
      }
      return null;
    },
    topSlot: (items) => (
      <>
        <StatsRow stats={[{ label: 'Applications', value: items.length, icon: Target, tone: 'indigo' }, { label: 'Shortlisted+', value: count(items, (a) => ['Shortlisted', 'Aptitude', 'Technical', 'HR', 'Selected'].includes(a.stage)), icon: Sparkles, tone: 'violet' },
          { label: 'Selected', value: count(items, (a) => a.stage === 'Selected'), icon: CheckCircle2, tone: 'aqua' }, { label: 'Rejected', value: count(items, (a) => a.stage === 'Rejected'), icon: XCircle, tone: 'coral' }]} />
        <Card className="!p-5"><div className="flex gap-2 flex-wrap">{STAGES.slice(0, 6).map((s) => <div key={s} className="flex-1 min-w-[110px] rounded-xl bg-canvas px-4 py-3"><p className="text-[12px] font-semibold text-mute uppercase">{s}</p><p className="font-num font-extrabold text-[24px]">{count(items, (a) => a.stage === s)}</p></div>)}</div></Card>
      </>),
  };
  return <ResourcePage cfg={cfg} refreshKey={k} />;
}
