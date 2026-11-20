import { useState } from 'react';
import { Download, Filter, Percent, TrendingUp, Trophy, Users, Building2, Briefcase, Award, Layers } from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';
import { useUI } from '../../../context/UIContext';
import { api, qs } from '../../../lib/api';
import { Button, Card, ErrorNote, PageHeader, SelectInput, Skeleton, StatCard, Progress, downloadBlob, useFetch } from '../../ui/kit';
import { BarC, LineC, MultiBar, PALETTE, PieC } from '../charts';
import { MotionDiv } from './motionDiv';
import { fmtDate } from '../../../lib/format';

interface A {
  filters: { department: string | null; batch: string | null; batches: string[] };
  kpis: Record<string, number>;
  departmentComparison: any[]; yearOverYear: any[]; funnel: any[]; salaryDistribution: any[]; placementTrend: any[]; vacancyTrend: any[];
  locationDistribution: any[]; companyActivity: any[]; internshipPerformance: { status: any[]; avgProgress: number; ppoConversion: number; total: number }; records: any[];
}

const Section = ({ title, sub, children, className }: { title: string; sub?: string; children: React.ReactNode; className?: string }) => (
  <MotionDiv className={className}><Card hover className="h-full"><h3 className="text-[17px] font-bold">{title}</h3>{sub && <p className="text-[13.5px] text-mute mb-3">{sub}</p>}<div className={sub ? '' : 'mt-3'}>{children}</div></Card></MotionDiv>
);

export default function AnalyticsView() {
  const { user, lookups, can } = useAuth();
  const { toast } = useUI();
  const [dept, setDept] = useState('');
  const [batch, setBatch] = useState('');
  const { data, loading, error, reload } = useFetch<A>(`/api/analytics${qs({ department: dept, batch })}`);
  const pinned = user!.role === 'department_tpo';

  const exportRecords = (fmt: 'csv' | 'xlsx') => {
    if (!data) return;
    if (fmt === 'xlsx' && can('reports:view')) { window.location.href = '/api/reports/export?dataset=placements&format=xlsx'; return; }
    const cols = ['rollNo', 'student', 'department', 'company', 'designation', 'ctcLpa', 'location', 'batch'];
    const esc = (v: any) => { const s = String(v ?? ''); return /^[=+\-@]/.test(s) ? `'${s}` : s; };
    const csv = [cols.join(','), ...data.records.map((r) => cols.map((c) => `"${esc(r[c]).replace(/"/g, '""')}"`).join(','))].join('\n');
    downloadBlob(new Blob(['\ufeff' + csv], { type: 'text/csv' }), 'placement_analytics.csv');
    toast('Filtered records exported');
  };
  void api;

  return (
    <div className="space-y-7">
      <PageHeader hero title="Analytics & insights" subtitle="Every number is computed from the placement records you are authorised to see. No estimates, no placeholders."
        actions={<><Button variant="secondary" onClick={() => exportRecords('csv')}><Download className="w-4 h-4" />CSV</Button>{can('reports:view') && <Button variant="secondary" onClick={() => exportRecords('xlsx')}><Download className="w-4 h-4" />Excel</Button>}</>} />

      <Card className="!p-4 flex flex-wrap items-center gap-3">
        <Filter className="w-4 h-4 text-violet ml-1" /><span className="font-semibold text-[14px]">Filters</span>
        <SelectInput className="w-auto min-w-[200px]" value={pinned ? user!.departmentCode ?? '' : dept} disabled={pinned} onChange={(e) => setDept(e.target.value)} aria-label="Department">
          <option value="">All departments</option>{lookups.departments?.map((d) => <option key={d.id} value={d.code}>{d.label}</option>)}
        </SelectInput>
        <SelectInput className="w-auto min-w-[160px]" value={batch} onChange={(e) => setBatch(e.target.value)} aria-label="Batch"><option value="">All batches</option>{data?.filters.batches.map((b) => <option key={b}>{b}</option>)}</SelectInput>
        {pinned && <span className="text-[13px] text-mute">Pinned to your department</span>}
      </Card>

      {error ? <ErrorNote message={error} onRetry={reload} /> : loading || !data ? (
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-5">{[...Array(8)].map((_, i) => <Skeleton key={i} className="h-36" />)}</div>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-5">
            <StatCard index={0} label="Placement %" value={data.kpis.placementRate} suffix="%" hint={`${data.kpis.placed} of ${data.kpis.students} students`} icon={Percent} tone="indigo" />
            <StatCard index={1} label="Average package" value={data.kpis.avgCtc} hint="LPA · accepted offers" icon={TrendingUp} tone="aqua" />
            <StatCard index={2} label="Highest package" value={data.kpis.highestCtc} hint={`Median ${data.kpis.medianCtc} LPA`} icon={Trophy} tone="coral" />
            <StatCard index={3} label="Offers" value={data.kpis.offers} hint={`${data.kpis.companies} hiring companies`} icon={Award} tone="violet" />
            <StatCard index={4} label="Students" value={data.kpis.students} icon={Users} tone="indigo" />
            <StatCard index={5} label="Companies hiring" value={data.kpis.companies} icon={Building2} tone="aqua" />
            <StatCard index={6} label="Vacancies" value={data.kpis.vacancies} icon={Briefcase} tone="coral" />
            <StatCard index={7} label="Internship PPO rate" value={data.internshipPerformance.ppoConversion} suffix="%" hint={`${data.internshipPerformance.total} internships`} icon={Layers} tone="violet" />
          </div>

          <div className="grid xl:grid-cols-2 gap-6">
            <Section title="Placement trend" sub="Accepted offers by month"><LineC data={data.placementTrend} area /></Section>
            <Section title="Department-wise comparison" sub="Placement % and average package (LPA)"><MultiBar data={data.departmentComparison.map((d) => ({ name: d.code, rate: d.rate, avg: d.avgCtc }))} keys={[{ key: 'rate', name: 'Placement %', color: PALETTE[0] }, { key: 'avg', name: 'Avg CTC', color: PALETTE[1] }]} /></Section>
            <Section title="Salary distribution" sub="Accepted offers by package band (LPA)"><BarC data={data.salaryDistribution} color={1} /></Section>
            <Section title="Recruitment conversion funnel" sub="Applications reaching each stage">
              <div className="space-y-3 pt-1">{data.funnel.map((f, i) => { const top = data.funnel[0].value || 1; return (
                <div key={f.name}><div className="flex justify-between text-[14px] mb-1.5"><span className="font-semibold">{f.name}</span><span className="font-num font-bold">{f.value}</span></div><Progress value={(f.value / top) * 100} tone={['indigo', 'violet', 'aqua', 'coral', 'lime', 'aqua'][i]} /></div>); })}</div>
            </Section>
            <Section title="Year-over-year comparison" sub="By batch: placement % and average CTC"><MultiBar data={data.yearOverYear.map((y) => ({ name: y.name, rate: y.rate, avg: y.avgCtc, hi: y.highestCtc }))} keys={[{ key: 'rate', name: 'Placement %', color: PALETTE[3] }, { key: 'avg', name: 'Avg CTC', color: PALETTE[1] }, { key: 'hi', name: 'Highest CTC', color: PALETTE[2], line: true }]} /></Section>
            <Section title="Specialisation-wise placement" sub="Students placed per specialisation"><BarC data={data.departmentComparison.map((d) => ({ name: d.name, value: d.placed }))} horizontal h={270} /></Section>
            <Section title="Location distribution" sub="Where offers are based"><PieC data={data.locationDistribution} /></Section>
            <Section title="Company recruitment activity" sub="Offers made by top companies"><BarC data={data.companyActivity.map((c) => ({ name: c.name, value: c.offers }))} horizontal color={2} h={270} /></Section>
            <Section title="Vacancy trend" sub="Vacancies created by month"><LineC data={data.vacancyTrend} /></Section>
            <Section title="Internship performance" sub={`Average progress ${data.internshipPerformance.avgProgress}% · PPO conversion ${data.internshipPerformance.ppoConversion}%`}><PieC data={data.internshipPerformance.status} /></Section>
          </div>

          <Card padded={false} className="overflow-hidden">
            <div className="p-5 border-b border-line"><h3 className="text-[17px] font-bold">Filtered offer records</h3><p className="text-[13.5px] text-mute">{data.records.length} records match the current filters</p></div>
            <div className="overflow-x-auto max-h-[420px]"><table className="tbl w-full min-w-[720px]"><thead><tr><th>Roll no</th><th>Student</th><th>Dept</th><th>Company</th><th>Designation</th><th>CTC (LPA)</th><th>Location</th></tr></thead>
              <tbody>{data.records.map((r, i) => <tr key={i}><td>{r.rollNo}</td><td className="font-semibold">{r.student}</td><td>{r.department}</td><td>{r.company}</td><td>{r.designation}</td><td className="font-num font-bold">{r.ctcLpa}</td><td>{r.location || '—'}</td></tr>)}</tbody></table>
              {!data.records.length && <p className="text-center text-mute py-10">No accepted offers match these filters.</p>}</div>
          </Card>
        </>
      )}
      <span className="hidden">{fmtDate(null)}</span>
    </div>
  );
}
