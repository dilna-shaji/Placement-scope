import { useState, useRef } from 'react';
import {
  GraduationCap, CheckCircle2, Clock, Target, Upload, Download,
  FileSpreadsheet, AlertCircle, CheckCircle, RefreshCw, X
} from 'lucide-react';
import { ResourcePage, type ResourceConfig } from '../../ui/ResourcePage';
import { StatusBadge, Badge, Button, Modal, Card } from '../../ui/kit';
import { useAuth } from '../../../context/AuthContext';
import { useUI } from '../../../context/UIContext';
import { StatsRow, count } from '../shared';

interface ImportSummary {
  dryRun: boolean;
  totalRows: number;
  imported: number;
  skipped: number;
  errors: { row: number; error: string }[];
}

function StudentImportModal({ open, onClose, onImported }: { open: boolean; onClose: () => void; onImported: () => void }) {
  const { toast } = useUI();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);

  const reset = () => {
    setFile(null);
    setSummary(null);
    setGeneralError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDownloadTemplate = async () => {
    try {
      const res = await fetch('/api/students/template', {
        headers: { Accept: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }
      });
      if (!res.ok) throw new Error('Failed to download template.');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'students_import_template.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast('Excel template downloaded');
    } catch (e: any) {
      toast(e.message || 'Download failed', 'error');
    }
  };

  const executeUpload = async (forceCommit = false) => {
    if (!file) {
      setGeneralError('Please choose an Excel (.xlsx) or CSV (.csv) file.');
      return;
    }
    setBusy(true);
    setGeneralError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const isDry = forceCommit ? false : dryRun;
      formData.append('dryRun', isDry ? 'true' : 'false');

      const res = await fetch('/api/students/import', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Import failed.');
      }
      setSummary(data);
      if (!isDry) {
        toast(`Successfully imported ${data.imported} student records`);
        onImported();
      } else {
        toast(`Dry-run validation complete: ${data.imported} ready, ${data.skipped} skipped, ${data.errors.length} errors`);
      }
    } catch (e: any) {
      setGeneralError(e.message || 'Import encountered an error.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={() => { reset(); onClose(); }} title="Bulk Student Import (Excel / CSV)" width="max-w-2xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <Button variant="ghost" size="sm" onClick={handleDownloadTemplate} className="text-indigo">
            <Download className="w-4 h-4" /> Download Official Template
          </Button>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => { reset(); onClose(); }}>Cancel</Button>
            {summary && summary.dryRun && summary.imported > 0 ? (
              <Button loading={busy} onClick={() => executeUpload(true)}>
                Commit Import ({summary.imported} Records)
              </Button>
            ) : (
              <Button loading={busy} disabled={!file} onClick={() => executeUpload(false)}>
                {dryRun ? 'Validate (Dry Run)' : 'Upload & Import'}
              </Button>
            )}
          </div>
        </div>
      }>
      <div className="space-y-5 text-ink">
        <p className="text-[14px] text-mute">
          Upload an official Excel workbook (<code>.xlsx</code>) or CSV file. The system validates roll numbers, e-mail uniqueness, department codes, and numeric CGPA values.
        </p>

        {generalError && (
          <div className="p-3.5 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] text-[13.5px] flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{generalError}</span>
          </div>
        )}

        <div className="border-2 border-dashed border-line hover:border-violet/60 transition rounded-2xl p-6 text-center bg-canvas/50">
          <FileSpreadsheet className="w-10 h-10 text-violet mx-auto mb-2 opacity-80" />
          <p className="font-semibold text-[15px]">{file ? file.name : 'Choose an Excel or CSV file'}</p>
          <p className="text-[12.5px] text-mute mt-1">
            {file ? `${(file.size / 1024).toFixed(1)} KB` : 'Drag and drop or browse from your computer'}
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            className="hidden"
            id="student-file-upload"
            onChange={(e) => {
              const selected = e.target.files?.[0] || null;
              setFile(selected);
              setSummary(null);
              setGeneralError(null);
            }}
          />
          <label htmlFor="student-file-upload" className="inline-block mt-4">
            <span className="px-4 py-2 rounded-xl text-[13.5px] font-semibold bg-white border border-line text-ink hover:border-violet cursor-pointer transition shadow-xs">
              Select File
            </span>
          </label>
        </div>

        <div className="flex items-center justify-between p-3.5 rounded-xl bg-canvas border border-line/70">
          <div>
            <p className="font-semibold text-[13.5px]">Dry Run Validation Mode</p>
            <p className="text-[12.5px] text-mute">Check for errors without saving to the database</p>
          </div>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="w-5 h-5 accent-[#2457A7] rounded cursor-pointer"
          />
        </div>

        {summary && (
          <div className="space-y-3 pt-2 border-t border-line">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded-xl bg-aqua/10 border border-aqua/30">
                <p className="text-[11px] font-bold uppercase text-[#0e7a7c]">Ready to Import</p>
                <p className="text-[22px] font-extrabold font-num text-[#0e7a7c]">{summary.imported}</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-100 border border-slate-200">
                <p className="text-[11px] font-bold uppercase text-slate-600">Skipped (Exists)</p>
                <p className="text-[22px] font-extrabold font-num text-slate-700">{summary.skipped}</p>
              </div>
              <div className={`p-3 rounded-xl ${summary.errors.length ? 'bg-coral/10 border border-coral/30' : 'bg-slate-100 border border-slate-200'}`}>
                <p className={`text-[11px] font-bold uppercase ${summary.errors.length ? 'text-[#c2412b]' : 'text-slate-600'}`}>Errors</p>
                <p className={`text-[22px] font-extrabold font-num ${summary.errors.length ? 'text-[#c2412b]' : 'text-slate-700'}`}>{summary.errors.length}</p>
              </div>
            </div>

            {summary.errors.length > 0 && (
              <div className="max-h-48 overflow-y-auto rounded-xl border border-coral/30 p-3 bg-coral/5 text-[12.5px] space-y-1.5">
                <p className="font-bold text-[#c2412b] mb-1">Validation Errors Found:</p>
                {summary.errors.map((err, i) => (
                  <div key={i} className="flex gap-2 text-ink/90">
                    <span className="font-mono font-bold text-[#c2412b]">Row {err.row}:</span>
                    <span>{err.error}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function StudentManagementView() {
  const { user, can } = useAuth();
  const { toast } = useUI();
  const [importOpen, setImportOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastItems, setLastItems] = useState<any[]>([]);

  const tpo = user!.role === 'department_tpo';

  const exportStudentsCsv = () => {
    if (!lastItems.length) {
      toast('No student records loaded to export', 'error');
      return;
    }
    const headers = ['Roll No', 'Name', 'Email', 'Phone', 'Department', 'Batch', 'CGPA', 'Active Backlogs', 'Status', 'Internship Status', 'Skills'];
    const rows = lastItems.map((s) => [
      `"${s.rollNo || ''}"`,
      `"${(s.name || '').replace(/"/g, '""')}"`,
      `"${s.email || ''}"`,
      `"${s.phone || ''}"`,
      `"${s.departmentCode || s.departmentName || ''}"`,
      `"${s.batch || ''}"`,
      s.cgpa ?? '',
      s.activeBacklogs ?? 0,
      `"${s.status || ''}"`,
      `"${s.internshipStatus || ''}"`,
      `"${(s.skills || []).join('; ')}"`,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `students_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    toast(`Exported ${lastItems.length} student records to CSV`);
  };

  const cfg: ResourceConfig = {
    resource: 'students', singular: 'Student', title: 'Student management',
    subtitle: tpo || user!.role === 'student_coordinator' ? 'Students within your assigned scope.' : user!.role === 'corporate_recruiter' ? 'Candidates who applied to your company (limited profile).' : 'Profiles, eligibility and placement status across all departments.',
    searchPlaceholder: 'Search name, roll number or e-mail…',
    defaults: { departmentId: tpo ? user!.departmentId : '', status: 'Unplaced', internshipStatus: 'None', activeBacklogs: 0, historyBacklogs: 0, cgpa: '' },
    filters: [{ name: 'departmentId', label: 'Department', lookup: 'departments' }, { name: 'status', label: 'Status', options: [{ value: '!Placed', label: 'Not placed' }, 'Placed', 'In Process', 'Unplaced', 'Opted Out'] }],
    fields: [
      { name: 'name', label: 'Full name', required: true }, { name: 'rollNo', label: 'Roll number', required: true, hint: 'Must be unique' },
      { name: 'email', label: 'E-mail', type: 'email', required: true }, { name: 'phone', label: 'Phone' },
      { name: 'departmentId', label: 'Department / specialisation', type: 'lookup', lookup: 'departments', required: true },
      { name: 'batch', label: 'Batch', required: true, placeholder: '2025-27' },
      { name: 'cgpa', label: 'CGPA (0–10)', type: 'number', step: '0.01' }, { name: 'activeBacklogs', label: 'Active backlogs', type: 'number' },
      { name: 'historyBacklogs', label: 'Backlog history', type: 'number' },
      { name: 'status', label: 'Placement status', type: 'select', options: ['Unplaced', 'In Process', 'Placed', 'Opted Out'] },
      { name: 'internshipStatus', label: 'Internship status', type: 'select', options: ['None', 'Ongoing', 'Completed', 'PPO Converted'] },
      { name: 'preferredDomain', label: 'Preferred domain' },
      { name: 'coordinatorId', label: 'Student coordinator', type: 'lookup', lookup: 'coordinators', hideFor: () => !can('students:write') },
      { name: 'skills', label: 'Skills', type: 'tags', span: 2, placeholder: 'Excel, SQL, Power BI' },
    ],
    columns: [
      { key: 'name', label: 'Student', render: (r) => <div><p className="font-semibold">{r.name}</p><p className="text-[13px] text-mute">{r.rollNo}{r.email ? ` · ${r.email}` : ''}</p></div> },
      { key: 'departmentName', label: 'Department', render: (r) => <Badge tone="violet">{r.departmentCode}</Badge> },
      { key: 'batch', label: 'Batch' },
      { key: 'cgpa', label: 'CGPA', render: (r) => <span className="font-num font-bold">{Number(r.cgpa).toFixed(2)}</span>, sort: (r) => r.cgpa },
      { key: 'activeBacklogs', label: 'Backlogs' },
      ...(user!.role === 'corporate_recruiter' ? [{ key: 'skills', label: 'Skills', render: (r: any) => (r.skills || []).join(', ') || '—' }] : [
        { key: 'status', label: 'Status', render: (r: any) => <StatusBadge value={r.status} /> },
        { key: 'coordinatorName', label: 'Coordinator', render: (r: any) => r.coordinatorName || <span className="text-mute">—</span> }]),
    ],
    canCreate: () => can('students:write'),
    headerActions: (
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="md" onClick={exportStudentsCsv} title="Export current list to CSV">
          <Download className="w-4 h-4" /> Export CSV
        </Button>
        {can('students:write') && (
          <Button variant="secondary" size="md" onClick={() => setImportOpen(true)} title="Bulk upload Excel or CSV file">
            <Upload className="w-4 h-4 text-violet" /> Bulk Excel Import
          </Button>
        )}
      </div>
    ),
    topSlot: (items) => {
      // Keep reference for export
      if (items !== lastItems) {
        setTimeout(() => setLastItems(items), 0);
      }
      return (
        <StatsRow stats={[
          { label: 'Students', value: items.length, hint: 'in your view', icon: GraduationCap, tone: 'indigo' },
          { label: 'Placed', value: count(items, (s) => s.status === 'Placed'), hint: 'accepted offers', icon: CheckCircle2, tone: 'aqua' },
          { label: 'In process', value: count(items, (s) => s.status === 'In Process'), icon: Clock, tone: 'violet' },
          { label: 'Unplaced', value: count(items, (s) => s.status === 'Unplaced'), hint: 'need attention', icon: Target, tone: 'coral' }]} />
      );
    },
  };

  return (
    <>
      <ResourcePage cfg={cfg} refreshKey={refreshKey} />
      <StudentImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={() => {
          setImportOpen(false);
          setRefreshKey((k) => k + 1);
        }}
      />
    </>
  );
}
