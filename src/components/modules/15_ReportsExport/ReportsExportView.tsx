import { Download, FileSpreadsheet, FileText } from 'lucide-react';
import { Card, Button, PageHeader, ErrorNote, Skeleton, useFetch, downloadBlob } from '../../ui/kit';
import { useUI } from '../../../context/UIContext';
import { camelToWords } from '../../../lib/format';
import { motion } from 'motion/react';

interface DS { name: string; columns: string[]; count: number }
const TITLES: Record<string, string> = { students: 'Student register', companies: 'Company directory', vacancies: 'Vacancy list', applications: 'Applications & stages', placements: 'Placement offers', internships: 'Internship tracker', drives: 'Recruitment drives', audit: 'Audit log' };

export default function ReportsExportView() {
  const { toast } = useUI();
  const { data, loading, error, reload } = useFetch<{ datasets: DS[] }>('/api/reports/datasets');
  const get = async (name: string, fmt: 'csv' | 'xlsx') => {
    const r = await fetch(`/api/reports/export?dataset=${name}&format=${fmt}`, { credentials: 'same-origin' });
    if (!r.ok) { toast((await r.json().catch(() => ({}))).error || 'Export failed', 'error'); return; }
    downloadBlob(await r.blob(), `${name}.${fmt}`);
    toast(`${TITLES[name]} exported`);
  };
  return (
    <div className="space-y-7">
      <PageHeader title="Reports & export" subtitle="Download records as CSV or Excel. Exports contain only what your role is allowed to see, and every export is audit-logged." />
      {error ? <ErrorNote message={error} onRetry={reload} /> : loading ? <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-44" />)}</div> : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {data!.datasets.map((d, i) => (
            <motion.div key={d.name} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * .05 }}>
              <Card hover className="h-full flex flex-col">
                <div className="flex items-center gap-3"><div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-indigo to-violet text-white grid place-items-center"><FileText className="w-5 h-5" /></div>
                  <div><h3 className="font-bold text-[17px]">{TITLES[d.name] ?? d.name}</h3><p className="text-[13.5px] text-mute">{d.count} record{d.count === 1 ? '' : 's'}</p></div></div>
                <p className="text-[13px] text-mute mt-4 flex-1 line-clamp-2">{d.columns.map(camelToWords).join(' · ')}</p>
                <div className="flex gap-2 mt-5"><Button size="sm" variant="secondary" onClick={() => get(d.name, 'csv')}><Download className="w-4 h-4" />CSV</Button><Button size="sm" onClick={() => get(d.name, 'xlsx')}><FileSpreadsheet className="w-4 h-4" />Excel</Button></div>
              </Card>
            </motion.div>))}
        </div>)}
    </div>
  );
}
