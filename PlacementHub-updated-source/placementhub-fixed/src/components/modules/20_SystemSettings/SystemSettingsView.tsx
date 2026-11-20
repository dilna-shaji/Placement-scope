import { useEffect, useState } from 'react';
import { Save } from 'lucide-react';
import { api, ApiError } from '../../../lib/api';
import { useUI } from '../../../context/UIContext';
import { Button, Card, ErrorNote, Field, PageHeader, Skeleton, TextArea, TextInput, useFetch } from '../../ui/kit';
import type { Row } from '../../../types';

const GROUPS: { title: string; sub: string; fields: { k: string; label: string; type?: string; hint?: string; area?: boolean }[] }[] = [
  { title: 'Institution', sub: 'Shown in headers and exports.', fields: [{ k: 'institution_name', label: 'Institution name' }, { k: 'academic_year', label: 'Current academic year', hint: 'e.g. 2025-26' }] },
  { title: 'Authentication & sessions', sub: 'Applied immediately to every sign-in.', fields: [
    { k: 'max_failed_logins', label: 'Failed attempts before lockout', type: 'number', hint: '3 – 20' }, { k: 'lockout_minutes', label: 'Base lockout (minutes)', type: 'number', hint: 'Doubles on each repeated lockout' },
    { k: 'session_idle_minutes', label: 'Idle session timeout (minutes)', type: 'number', hint: '5 – 480' }, { k: 'password_min_length', label: 'Minimum password length', type: 'number', hint: '8 – 64' }] },
  { title: 'Placement policy', sub: 'Reference values for the placement cell.', fields: [{ k: 'min_cgpa_default', label: 'Default minimum CGPA', type: 'number' }, { k: 'max_offers_per_student', label: 'Max offers per student', type: 'number' }, { k: 'placement_policy_note', label: 'Policy note', area: true }] },
];

export default function SystemSettingsView() {
  const { toast } = useUI();
  const { data, loading, error, reload } = useFetch<{ settings: Row }>('/api/settings');
  const [v, setV] = useState<Row>({}); const [errs, setErrs] = useState<Record<string, string>>({}); const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setV(data.settings); }, [data]);
  const save = async () => {
    setBusy(true); setErrs({});
    try { await api.put('/api/settings', v); toast('Settings saved'); reload(); } catch (e) { setErrs((e as ApiError).fields || {}); toast((e as ApiError).message, 'error'); } finally { setBusy(false); }
  };
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  return (
    <div className="space-y-7">
      <PageHeader title="System settings" subtitle="Institution-wide configuration. Every change is audit-logged." actions={<Button loading={busy} onClick={save}><Save className="w-4 h-4" />Save changes</Button>} />
      {loading ? <Skeleton className="h-96" /> : GROUPS.map((g) => (
        <Card key={g.title}><h3 className="font-bold text-[18px]">{g.title}</h3><p className="text-[14px] text-mute mb-5">{g.sub}</p>
          <div className="grid md:grid-cols-2 gap-5">{g.fields.map((f) => (
            <Field key={f.k} label={f.label} hint={f.hint} error={errs[f.k]} className={f.area ? 'md:col-span-2' : ''}>
              {f.area ? <TextArea value={v[f.k] ?? ''} onChange={(e) => setV({ ...v, [f.k]: e.target.value })} /> : <TextInput type={f.type || 'text'} value={v[f.k] ?? ''} onChange={(e) => setV({ ...v, [f.k]: e.target.value })} invalid={!!errs[f.k]} />}
            </Field>))}</div></Card>))}
    </div>
  );
}
