import { useState } from 'react';
import { motion } from 'motion/react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { Card, Progress, useFetch } from '../../ui/kit';
import { BarC } from '../charts';
import type { Row } from '../../../types';

export default function AcademicDepartmentView() {
  const [k, setK] = useState(0);
  const { data } = useFetch<{ items: Row[] }>('/api/departments-stats', [k]);
  const stats = data?.items ?? [];
  const cfg: ResourceConfig = {
    resource: 'departments', singular: 'Department', title: 'Academic & department management', subtitle: 'Specialisations, intake and live placement performance.',
    onMutation: () => setK((x) => x + 1),
    defaults: { intake: 0 },
    fields: [{ name: 'code', label: 'Code', required: true, hint: 'e.g. MKT' }, { name: 'name', label: 'Department / specialisation', required: true }, { name: 'hodName', label: 'Head of department' }, { name: 'intake', label: 'Annual intake', type: 'number' }],
    columns: [
      { key: 'name', label: 'Department', render: (r) => <div><p className="font-semibold">{r.name}</p><p className="text-[13px] text-mute">{r.code} · HoD {r.hodName || '—'}</p></div> },
      { key: 'intake', label: 'Intake' },
      { key: 'totalStudents', label: 'Students', render: (r) => stats.find((s) => s.id === r.id)?.totalStudents ?? '—' },
      { key: 'rate', label: 'Placement rate', render: (r) => { const s = stats.find((x) => x.id === r.id); return s ? <div className="flex items-center gap-3 min-w-[160px]"><Progress value={s.placementRate} /><span className="font-num font-bold text-[13px]">{s.placementRate}%</span></div> : '—'; } },
      { key: 'avg', label: 'Avg / highest CTC', render: (r) => { const s = stats.find((x) => x.id === r.id); return s ? `${s.avgCtcLpa} / ${s.highestCtcLpa} LPA` : '—'; } },
    ],
    topSlot: () => (
      <div className="grid xl:grid-cols-[1.2fr_1fr] gap-6">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {stats.map((s, i) => (
            <motion.div key={s.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * .06 }}>
              <Card hover className="h-full"><p className="text-[12px] font-bold uppercase tracking-wider text-violet">{s.code}</p><h3 className="font-extrabold text-[18px] mt-1">{s.name}</h3>
                <p className="font-num font-extrabold text-[34px] mt-3">{s.placementRate}<span className="text-[18px] text-mute">%</span></p><Progress value={s.placementRate} tone="aqua" />
                <p className="text-[13.5px] text-mute mt-3">{s.placedStudents} of {s.totalStudents} students placed</p></Card>
            </motion.div>))}
        </div>
        <Card><h3 className="font-bold text-[17px] mb-3">Placement rate by department (%)</h3><BarC data={stats.map((s) => ({ name: s.code, value: s.placementRate }))} h={250} /></Card>
      </div>),
  };
  return <ResourcePage cfg={cfg} refreshKey={k} />;
}
