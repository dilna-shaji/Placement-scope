import { motion } from 'motion/react';
import { Building2, MapPin, Mail, Phone, Globe } from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';
import { Badge, Card, ErrorNote, PageHeader, Skeleton, StatCard, StatusBadge, useFetch } from '../../ui/kit';
import { BarC, LineC, PieC } from '../charts';
import { useUI } from '../../../context/UIContext';

interface Widget { type: 'bar' | 'line' | 'pie' | 'list'; title: string; data: any[] }
interface Dash { role: string; title: string; kpis: { label: string; value: number; hint: string; tone: string; suffix: string }[]; widgets: Widget[]; profile?: Record<string, any> | null }

const greet = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; };

export default function DashboardView() {
  const { user } = useAuth();
  const { navigate } = useUI();
  const { data, loading, error, reload } = useFetch<Dash>('/api/dashboard');
  if (error) return <ErrorNote message={error} onRetry={reload} />;

  return (
    <div className="space-y-7">
      <PageHeader hero title={`${greet()}, ${user!.fullName.split(' ')[0]}`} subtitle={data?.title ?? 'Loading your workspace…'}
        actions={<Badge tone="lime">{user!.roleLabel}</Badge>} />
      {loading || !data ? (
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-5">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-36" />)}</div>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-5">{data.kpis.map((k, i) => <StatCard key={k.label} index={i} label={k.label} value={k.value} hint={k.hint} tone={k.tone} suffix={k.suffix} />)}</div>
          {data.profile && (
            <Card className="relative overflow-hidden">
              <div className="flex flex-wrap items-start justify-between gap-5">
                <div className="flex gap-4"><div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo to-violet text-white grid place-items-center"><Building2 className="w-7 h-7" /></div>
                  <div><h3 className="text-[20px] font-extrabold">{data.profile.name}</h3><p className="text-mute">{data.profile.industry || 'Industry not set'} · {data.profile.tier}</p>
                    <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-[14px] text-ink/80">
                      {data.profile.location && <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4 text-violet" />{data.profile.location}</span>}
                      {data.profile.contactEmail && <span className="flex items-center gap-1.5"><Mail className="w-4 h-4 text-violet" />{data.profile.contactEmail}</span>}
                      {data.profile.contactPhone && <span className="flex items-center gap-1.5"><Phone className="w-4 h-4 text-violet" />{data.profile.contactPhone}</span>}
                      {data.profile.website && <span className="flex items-center gap-1.5"><Globe className="w-4 h-4 text-violet" />{data.profile.website}</span>}
                    </div></div></div>
                <div className="flex gap-2 items-center"><StatusBadge value={data.profile.mouStatus} /><button onClick={() => navigate('companies')} className="text-indigo font-semibold text-[14px] hover:underline">Edit profile</button></div>
              </div>
            </Card>
          )}
          <div className="grid lg:grid-cols-2 gap-6">
            {data.widgets.map((w, i) => (
              <motion.div key={w.title} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .2 + i * .07 }}>
                <Card hover className="h-full">
                  <h3 className="text-[17px] font-bold mb-4">{w.title}</h3>
                  {w.type === 'bar' && <BarC data={w.data} />}{w.type === 'line' && <LineC data={w.data} area />}{w.type === 'pie' && <PieC data={w.data} />}
                  {w.type === 'list' && (w.data.length ? (
                    <ul className="divide-y divide-line">{w.data.map((it, j) => (
                      <li key={j} className="py-3 flex items-center justify-between gap-3"><div className="min-w-0"><p className="font-semibold truncate">{it.title}</p><p className="text-[13.5px] text-mute truncate">{it.subtitle}</p></div>
                        <div className="text-right shrink-0"><p className="text-[13px] text-mute">{it.meta}</p>{it.badge && <StatusBadge value={it.badge} />}</div></li>))}</ul>
                  ) : <p className="text-mute text-[14px] py-8 text-center">Nothing to show yet.</p>)}
                </Card>
              </motion.div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
