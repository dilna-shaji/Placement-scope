import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronLeft, ChevronRight, Pencil, Plus, Search, Trash2, ArrowUpDown } from 'lucide-react';
import { api, ApiError, qs } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import { useUI } from '../../context/UIContext';
import type { AuthUser, Page, Row } from '../../types';
import { Badge, Button, Card, ConfirmDialog, Empty, ErrorNote, Field, Modal, PageHeader, SelectInput, Skeleton, TextArea, TextInput, useFetch } from './kit';
import { cn } from '../../lib/format';

export type Opt = string | { value: string | number; label: string };
export interface FieldDef {
  name: string; label: string;
  type?: 'text' | 'email' | 'number' | 'date' | 'textarea' | 'select' | 'multi' | 'tags' | 'checkbox' | 'lookup';
  options?: Opt[]; lookup?: 'departments' | 'companies' | 'students' | 'vacancies' | 'coordinators';
  required?: boolean; hint?: string; placeholder?: string; span?: 2; step?: string;
  hideFor?: (u: AuthUser) => boolean; createOnly?: boolean; optional?: boolean;
}
export interface ColumnDef { key: string; label: string; render?: (r: Row) => ReactNode; sort?: (r: Row) => string | number }
export interface FilterDef { name: string; label: string; options?: Opt[]; lookup?: 'companies' | 'departments' }
export interface ResourceConfig {
  resource: string; singular: string; title: string; subtitle: string;
  fields: FieldDef[]; columns: ColumnDef[]; filters?: FilterDef[]; searchPlaceholder?: string;
  canCreate?: (u: AuthUser) => boolean; canEditRow?: (r: Row, u: AuthUser) => boolean; canDeleteRow?: (r: Row, u: AuthUser) => boolean;
  rowActions?: (r: Row, reload: () => void) => ReactNode; headerActions?: ReactNode;
  topSlot?: (items: Row[], total: number) => ReactNode; defaults?: Row; noSearch?: boolean;
  onMutation?: () => void;
}

const opt = (o: Opt) => (typeof o === 'string' ? { value: o, label: o } : o);
const PAGE = 12;

function useOptions(f: FieldDef | FilterDef) {
  const { lookups } = useAuth();
  if ('lookup' in f && f.lookup) {
    const src = (lookups as any)[f.lookup] as { id: number; label: string; code?: string }[] | undefined;
    return (src || []).map((x) => ({ value: (f as FieldDef).type === 'multi' ? x.code ?? x.id : x.id, label: x.label }));
  }
  return (f.options || []).map(opt);
}

function FieldInput({ f, value, onChange, error }: { f: FieldDef; value: any; onChange: (v: any) => void; error?: string }) {
  const options = useOptions(f);
  const t = f.type || 'text';
  let input: ReactNode;
  if (t === 'textarea') input = <TextArea value={value ?? ''} onChange={(e) => onChange(e.target.value)} invalid={!!error} placeholder={f.placeholder} />;
  else if (t === 'select' || t === 'lookup')
    input = (
      <SelectInput value={value ?? ''} onChange={(e) => onChange(e.target.value === '' ? '' : t === 'lookup' ? Number(e.target.value) : e.target.value)} invalid={!!error}>
        <option value="">{f.required ? 'Select…' : '— None —'}</option>
        {options.map((o) => <option key={String(o.value)} value={o.value}>{o.label}</option>)}
      </SelectInput>
    );
  else if (t === 'multi') {
    const arr: string[] = Array.isArray(value) ? value : [];
    input = (
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = arr.includes(String(o.value));
          return (
            <button type="button" key={String(o.value)} onClick={() => onChange(on ? arr.filter((x) => x !== String(o.value)) : [...arr, String(o.value)])}
              className={cn('px-3 py-1.5 rounded-full text-[13.5px] font-semibold border transition', on ? 'bg-indigo text-white border-indigo' : 'bg-white border-line text-ink/80 hover:border-violet')}>{o.label}</button>
          );
        })}
      </div>
    );
  } else if (t === 'tags')
    input = <TextInput value={Array.isArray(value) ? value.join(', ') : value ?? ''} onChange={(e) => onChange(e.target.value.split(',').map((x) => x.trimStart()))} placeholder={f.placeholder || 'Comma separated'} />;
  else if (t === 'checkbox')
    input = <label className="flex items-center gap-3 py-2.5 cursor-pointer"><input type="checkbox" className="w-5 h-5 accent-[#5146D8]" checked={!!value} onChange={(e) => onChange(e.target.checked)} /><span className="text-[15px]">{f.hint || 'Yes'}</span></label>;
  else input = <TextInput type={t} step={f.step} value={value ?? ''} onChange={(e) => onChange(t === 'number' ? e.target.value : e.target.value)} invalid={!!error} placeholder={f.placeholder} />;
  return <Field label={f.label} required={f.required} error={error} hint={t === 'checkbox' ? undefined : f.hint} className={f.span === 2 || t === 'textarea' || t === 'multi' ? 'sm:col-span-2' : ''}>{input}</Field>;
}

export function RecordForm({ cfg, row, onClose, onSaved }: { cfg: ResourceConfig; row: Row | null; onClose: () => void; onSaved: () => void }) {
  const { user, refreshLookups } = useAuth();
  const { toast } = useUI();
  const editing = !!row;
  const fields = cfg.fields.filter((f) => !(f.hideFor && user && f.hideFor(user)) && !(editing && f.createOnly));
  const [vals, setVals] = useState<Row>(() => ({ ...(cfg.defaults || {}), ...(row || {}) }));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState('');

  const submit = async () => {
    setBusy(true); setErrors({}); setFormErr('');
    const body: Row = {};
    fields.forEach((f) => {
      let v = vals[f.name];
      if (f.type === 'number' && v !== '' && v != null) v = Number(v);
      if (f.type === 'tags' && Array.isArray(v)) v = v.map((x: string) => x.trim()).filter(Boolean);
      if (v !== undefined) body[f.name] = v;
    });
    try {
      if (editing) await api.put(`/api/${cfg.resource}/${row!.id}`, body);
      else await api.post(`/api/${cfg.resource}`, body);
      toast(`${cfg.singular} ${editing ? 'updated' : 'created'}`);
      refreshLookups();
      onSaved();
    } catch (e) {
      const err = e as ApiError;
      setErrors(err.fields || {});
      setFormErr(err.message);
    } finally { setBusy(false); }
  };

  return (
    <Modal open onClose={onClose} title={`${editing ? 'Edit' : 'Add'} ${cfg.singular.toLowerCase()}`} width="max-w-3xl"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={submit}>{editing ? 'Save changes' : `Create ${cfg.singular.toLowerCase()}`}</Button></>}>
      {formErr && <div role="alert" className="mb-5 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">{formErr}</div>}
      <div className="grid sm:grid-cols-2 gap-x-5 gap-y-5">
        {fields.map((f) => <FieldInput key={f.name} f={f} value={vals[f.name]} onChange={(v) => setVals((s) => ({ ...s, [f.name]: v }))} error={errors[f.name]} />)}
      </div>
    </Modal>
  );
}

export function ResourcePage({ cfg, refreshKey = 0 }: { cfg: ResourceConfig; refreshKey?: number }) {
  const { user, can, lookups } = useAuth();
  const { toast } = useUI();
  const [q, setQ] = useState('');
  const [dq, setDq] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [editing, setEditing] = useState<Row | null | undefined>(undefined); // undefined = closed, null = new
  const [deleting, setDeleting] = useState<Row | null>(null);

  useEffect(() => { const t = setTimeout(() => { setDq(q); setPage(1); }, 250); return () => clearTimeout(t); }, [q]);
  const url = `/api/${cfg.resource}${qs({ q: dq, ...filters, pageSize: 1000 })}`;
  const { data, loading, error, reload } = useFetch<Page>(url, [refreshKey]);
  const items = data?.items ?? [];

  const sorted = useMemo(() => {
    if (!sort) return items;
    const col = cfg.columns.find((c) => c.key === sort.key);
    const get = (r: Row) => (col?.sort ? col.sort(r) : r[sort.key]);
    return [...items].sort((a, b) => (get(a) > get(b) ? 1 : get(a) < get(b) ? -1 : 0) * sort.dir);
  }, [items, sort, cfg.columns]);
  const pages = Math.max(1, Math.ceil(sorted.length / PAGE));
  const view = sorted.slice((page - 1) * PAGE, page * PAGE);

  const mayWrite = can(`${cfg.resource}:write`);
  const mayDelete = can(`${cfg.resource}:delete`);
  const mayCreate = mayWrite && (cfg.canCreate ? cfg.canCreate(user!) : true);

  const doDelete = async () => {
    try {
      await api.del(`/api/${cfg.resource}/${deleting!.id}`);
      toast(`${cfg.singular} deleted`);
      setDeleting(null);
      reload();
      cfg.onMutation?.();
    } catch (e) { toast((e as ApiError).message, 'error'); setDeleting(null); }
  };

  return (
    <div className="space-y-7">
      <PageHeader title={cfg.title} subtitle={cfg.subtitle}
        actions={<>{cfg.headerActions}{mayCreate && <Button onClick={() => setEditing(null)}><Plus className="w-4 h-4" />Add {cfg.singular.toLowerCase()}</Button>}</>} />
      {cfg.topSlot?.(items, data?.total ?? 0)}

      <Card padded={false} className="overflow-hidden">
        <div className="p-5 flex flex-wrap items-center gap-3 border-b border-line">
          {!cfg.noSearch && (
            <div className="relative flex-1 min-w-[220px] max-w-md">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-mute" />
              <TextInput className="pl-10" value={q} onChange={(e) => setQ(e.target.value)} placeholder={cfg.searchPlaceholder || 'Search…'} aria-label="Search" />
            </div>
          )}
          {cfg.filters?.map((f) => <FilterSelect key={f.name} f={f} value={filters[f.name] || ''} onChange={(v) => { setFilters((s) => ({ ...s, [f.name]: v })); setPage(1); }} />)}
          <span className="ml-auto text-[13.5px] text-mute">{loading ? 'Loading…' : `${sorted.length} record${sorted.length === 1 ? '' : 's'}`}</span>
        </div>

        {error ? <div className="p-6"><ErrorNote message={error} onRetry={reload} /></div>
          : loading && !data ? <div className="p-6 space-y-3">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
          : !view.length ? <Empty title={`No ${cfg.singular.toLowerCase()} records`} text={dq || Object.values(filters).some(Boolean) ? 'Nothing matches your search or filters.' : `Nothing here yet.${mayCreate ? '' : ''}`}
              action={mayCreate && !dq ? <Button onClick={() => setEditing(null)}><Plus className="w-4 h-4" />Add {cfg.singular.toLowerCase()}</Button> : undefined} />
          : (
            <div className="overflow-x-auto">
              <table className="tbl w-full min-w-[720px]">
                <thead><tr>
                  {cfg.columns.map((c) => (
                    <th key={c.key}><button className="inline-flex items-center gap-1.5 hover:text-indigo" onClick={() => setSort((s) => (s?.key === c.key ? { key: c.key, dir: (s.dir * -1) as 1 | -1 } : { key: c.key, dir: 1 }))}>{c.label}<ArrowUpDown className="w-3 h-3 opacity-50" /></button></th>
                  ))}
                  <th className="text-right">Actions</th>
                </tr></thead>
                <tbody>
                  <AnimatePresence initial={false}>
                    {view.map((r, i) => (
                      <motion.tr key={r.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * .02 }}>
                        {cfg.columns.map((c) => <td key={c.key}>{c.render ? c.render(r) : String(r[c.key] ?? '—')}</td>)}
                        <td>
                          <div className="flex justify-end items-center gap-1.5">
                            {r.isSample && <Badge tone="amber">Sample</Badge>}
                            {cfg.rowActions?.(r, reload)}
                            {mayWrite && (!cfg.canEditRow || cfg.canEditRow(r, user!)) && <button title="Edit" aria-label="Edit" onClick={() => setEditing(r)} className="p-2 rounded-lg text-mute hover:bg-indigo/10 hover:text-indigo transition"><Pencil className="w-4 h-4" /></button>}
                            {mayDelete && (!cfg.canDeleteRow || cfg.canDeleteRow(r, user!)) && <button title="Delete" aria-label="Delete" onClick={() => setDeleting(r)} className="p-2 rounded-lg text-mute hover:bg-coral/15 hover:text-[#c2412b] transition"><Trash2 className="w-4 h-4" /></button>}
                          </div>
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          )}
        {pages > 1 && (
          <div className="flex items-center justify-between px-5 py-3.5 border-t border-line text-[14px] text-mute">
            <span>Page {page} of {pages}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><ChevronLeft className="w-4 h-4" />Prev</Button>
              <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next<ChevronRight className="w-4 h-4" /></Button>
            </div>
          </div>
        )}
      </Card>

      {editing !== undefined && <RecordForm cfg={cfg} row={editing} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); reload(); cfg.onMutation?.(); }} />}
      <ConfirmDialog open={!!deleting} danger title={`Delete ${cfg.singular.toLowerCase()}?`} confirmLabel="Delete" message="This permanently removes the record and anything that depends on it. This action is written to the audit log." onConfirm={doDelete} onClose={() => setDeleting(null)} />
      <span className="hidden">{Object.keys(lookups).length}</span>
    </div>
  );
}

function FilterSelect({ f, value, onChange }: { f: FilterDef; value: string; onChange: (v: string) => void }) {
  const options = useOptions(f);
  return (
    <SelectInput className="w-auto min-w-[160px]" value={value} onChange={(e) => onChange(e.target.value)} aria-label={f.label}>
      <option value="">{f.label}: All</option>
      {options.map((o) => <option key={String(o.value)} value={o.value}>{o.label}</option>)}
    </SelectInput>
  );
}
