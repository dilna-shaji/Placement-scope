import { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2, FileUp, Download, XCircle, Play, RefreshCw, AlertTriangle,
  ShieldCheck, ShieldAlert, Clock, Sparkles, Filter, ExternalLink, ArrowRight
} from 'lucide-react';
import { api, ApiError } from '../../../lib/api';
import { useUI } from '../../../context/UIContext';
import { Badge, Button, Card, PageHeader, downloadBlob, StatCard, Skeleton } from '../../ui/kit';

interface Res {
  dryRun: boolean;
  total: number;
  valid: number;
  created: number;
  rows: { row: number; title: string; company: string; errors: string[] }[];
}

interface RunLog {
  id: number;
  source: string;
  query: string;
  status: string;
  discoveredCount: number;
  duplicatesCount: number;
  scamFlaggedCount: number;
  createdCount: number;
  durationSeconds: number;
  logs: string[];
  createdAt: string;
}

interface Summary {
  totalScraped: number;
  pendingVerification: number;
  approved: number;
  highRiskFlagged: number;
  lastRun: RunLog | null;
  serperConfigured: boolean;
}

const TEMPLATE = 'title,company,job_type,ctc_lpa,min_cgpa,openings,departments,locations,deadline,description\nMarketing Associate,Swiggy,Full-Time,8.5,6.5,5,MKT;BA,Mumbai;Pune,2026-12-20,Role summary\n';

export default function OpportunityImportView() {
  const { toast, navigate } = useUI();
  const [tab, setTab] = useState<'scraper' | 'csv'>('scraper');

  // Scraper pipeline states
  const [summary, setSummary] = useState<Summary | null>(null);
  const [runs, setRuns] = useState<RunLog[]>([]);
  const [sourceFilter, setSourceFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [activeLogs, setActiveLogs] = useState<string[]>([]);
  const [lastResult, setLastResult] = useState<any | null>(null);

  // CSV import states
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [res, setRes] = useState<Res | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [drag, setDrag] = useState(false);

  const loadScraperData = async () => {
    try {
      const [sumData, runsData] = await Promise.all([
        api.get<Summary>('/api/aggregation/summary'),
        api.get<{ items: RunLog[] }>('/api/aggregation/runs'),
      ]);
      setSummary(sumData);
      setRuns(runsData.items || []);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadScraperData();
  }, []);

  const triggerPipeline = async () => {
    setRunningPipeline(true);
    setActiveLogs(['[00:00:00] Initializing multi-source discovery pipeline...']);
    setLastResult(null);
    try {
      const res = await api.post<any>('/api/aggregation/run', {
        source: sourceFilter,
        query: searchQuery,
      });
      setLastResult(res);
      setActiveLogs(res.logs || []);
      toast(`Pipeline completed: ${res.created} draft vacancies created for verification.`);
      loadScraperData();
    } catch (e) {
      toast((e as ApiError).message);
    } finally {
      setRunningPipeline(false);
    }
  };

  const runCsv = async (dry: boolean) => {
    if (!file) return;
    setBusy(true);
    setErr('');
    const fd = new FormData();
    fd.append('file', file);
    fd.append('dryRun', String(dry));
    try {
      const r = await api.upload<Res>('/api/vacancies/import', fd);
      setRes(r);
      if (!dry) {
        toast(`${r.created} vacancies imported as drafts`);
        setFile(null);
      }
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-7">
      <PageHeader
        title="Opportunity Collection & Job Aggregation"
        subtitle="Automate institutional internship and job discovery across Greenhouse, Internshala, and LinkedIn, or batch import verified spreadsheets. All collected listings enter as Drafts."
        actions={
          <div className="flex gap-2">
            <Button
              variant={tab === 'scraper' ? 'primary' : 'secondary'}
              onClick={() => setTab('scraper')}
            >
              <RefreshCw className="w-4 h-4" />
              Automated Aggregator Pipeline
            </Button>
            <Button
              variant={tab === 'csv' ? 'primary' : 'secondary'}
              onClick={() => setTab('csv')}
            >
              <FileUp className="w-4 h-4" />
              CSV Spreadsheet Import
            </Button>
          </div>
        }
      />

      {tab === 'scraper' ? (
        <div className="space-y-6">
          {/* Summary KPIs */}
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <StatCard
              index={0}
              label="Aggregated Opportunities"
              value={summary?.totalScraped ?? 0}
              hint="total from web sources"
              tone="indigo"
            />
            <StatCard
              index={1}
              label="Pending Verification"
              value={summary?.pendingVerification ?? 0}
              hint="requiring cell approval"
              tone="coral"
            />
            <StatCard
              index={2}
              label="Approved & Live"
              value={summary?.approved ?? 0}
              hint="published to students"
              tone="lime"
            />
            <StatCard
              index={3}
              label="Risk Flagged"
              value={summary?.highRiskFlagged ?? 0}
              hint="fees/payment alerts detected"
              tone="violet"
            />
          </div>

          {/* Trigger Card */}
          <Card className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
              <div>
                <h3 className="text-[18px] font-bold flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-violet" />
                  Run Aggregation & Extraction Pipeline
                </h3>
                <p className="text-mute text-[14px]">
                  Executes the 5-stage discovery, source connector, detail extraction, deduplication, and scam-screening pipeline.
                </p>
              </div>
              <Button
                variant="primary"
                loading={runningPipeline}
                onClick={triggerPipeline}
                className="shadow-sm"
              >
                <Play className="w-4 h-4 fill-current" />
                Run Pipeline Now
              </Button>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-[13px] font-semibold text-mute block mb-1.5">
                  Source Connector
                </label>
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="w-full rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-[14.5px] font-medium"
                >
                  <option value="all">All Available Sources (Greenhouse, Internshala, LinkedIn, Curated)</option>
                  <option value="greenhouse">Greenhouse (Boards & Serper Google Search)</option>
                  <option value="internshala">Internshala (Public Internships Feed)</option>
                  <option value="linkedin">LinkedIn (Guest Job Listings)</option>
                </select>
              </div>

              <div>
                <label className="text-[13px] font-semibold text-mute block mb-1.5">
                  Search Query / Filter Expression (Optional)
                </label>
                <input
                  type="text"
                  placeholder='e.g. site:boards.greenhouse.io "intern" "India" or "data analyst"'
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-[14.5px]"
                />
              </div>
            </div>

            {/* Pipeline Notice & Security Standard */}
            <div className="rounded-xl bg-violet/8 border border-violet/20 p-4 flex items-start gap-3 text-[13.5px]">
              <ShieldCheck className="w-5 h-5 text-violet shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-ink">Institutional Verification & Anti-Scam Standard</p>
                <p className="text-mute mt-0.5">
                  Every aggregated opportunity is automatically normalized, deduplicated by URL and company identity, and screened for payment/fee demands.
                  Collected opportunities enter the system strictly as <b>Pending Verification</b> drafts. Students cannot view them until verified by the Placement Cell.
                </p>
              </div>
            </div>

            {/* Live Pipeline Execution Logs */}
            {activeLogs.length > 0 && (
              <div className="rounded-xl bg-[#0f111a] text-[#89ddff] p-4 font-mono text-[13px] space-y-1.5 max-h-56 overflow-y-auto">
                <div className="text-[#a6accd] font-bold border-b border-white/10 pb-1 mb-2 flex items-center justify-between">
                  <span>Pipeline Execution Telemetry</span>
                  {runningPipeline && <span className="animate-pulse text-[#c3e88d]">Running...</span>}
                </div>
                {activeLogs.map((log, idx) => (
                  <div key={idx} className="leading-relaxed">{log}</div>
                ))}
              </div>
            )}

            {lastResult && (
              <div className="flex items-center justify-between p-4 rounded-xl bg-lime/10 border border-lime/30 text-[#285c15] text-[14px]">
                <span>
                  <b>Run #{lastResult.run_id} Success:</b> Discovered {lastResult.discovered} opportunities · Created {lastResult.created} new draft vacancies · Skipped {lastResult.duplicates} duplicates · {lastResult.scam_flagged} flagged for manual scam review.
                </span>
                <Button size="sm" variant="secondary" onClick={() => navigate('vacancy-verification')}>
                  Go to Approvals <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            )}
          </Card>

          {/* Historical Pipeline Runs */}
          <Card padded={false} className="overflow-hidden">
            <div className="p-5 border-b border-line flex items-center justify-between">
              <h3 className="font-bold text-[17px]">Execution History & Audit Records</h3>
              <Button size="sm" variant="secondary" onClick={loadScraperData}>
                <RefreshCw className="w-4 h-4" /> Refresh
              </Button>
            </div>
            {runs.length === 0 ? (
              <div className="p-8 text-center text-mute text-[14px]">
                No pipeline runs recorded yet. Click "Run Pipeline Now" to execute initial job collection.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="tbl w-full min-w-[700px]">
                  <thead>
                    <tr>
                      <th>Run ID</th>
                      <th>Timestamp</th>
                      <th>Source Target</th>
                      <th>Discovered</th>
                      <th>Duplicates</th>
                      <th>Flagged Risk</th>
                      <th>Created Drafts</th>
                      <th>Duration</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.id}>
                        <td className="font-mono text-mute">#{r.id}</td>
                        <td className="font-medium text-[13.5px]">
                          {new Date(r.createdAt).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}
                        </td>
                        <td>
                          <Badge tone="indigo">{r.source}</Badge>
                        </td>
                        <td className="font-semibold">{r.discoveredCount}</td>
                        <td className="text-mute">{r.duplicatesCount}</td>
                        <td>
                          {r.scamFlaggedCount > 0 ? (
                            <Badge tone="coral">{r.scamFlaggedCount} flagged</Badge>
                          ) : (
                            <span className="text-mute text-[13px]">Clean</span>
                          )}
                        </td>
                        <td className="font-bold text-ink">{r.createdCount}</td>
                        <td className="text-mute font-mono text-[13px]">{r.durationSeconds}s</td>
                        <td>
                          <Badge tone={r.status === 'Success' ? 'lime' : 'coral'}>{r.status}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      ) : (
        /* CSV Spreadsheet Import Tab */
        <div className="space-y-6">
          <Card>
            <div className="flex items-center justify-between border-b border-line pb-4 mb-5">
              <div>
                <h3 className="font-bold text-[18px]">Batch Spreadsheet Upload</h3>
                <p className="text-mute text-[14px]">Upload pre-compiled CSV lists of vacancies directly into draft review status.</p>
              </div>
              <Button
                variant="secondary"
                onClick={() => downloadBlob(new Blob([TEMPLATE], { type: 'text/csv' }), 'vacancy_import_template.csv')}
              >
                <Download className="w-4 h-4" />
                Download Template
              </Button>
            </div>

            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDrag(false);
                const f = e.dataTransfer.files[0];
                if (f) { setFile(f); setRes(null); }
              }}
              onClick={() => input.current?.click()}
              className={`cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition ${
                drag ? 'border-violet bg-violet/8' : 'border-line hover:border-violet/60 hover:bg-canvas'
              }`}
            >
              <FileUp className="w-9 h-9 mx-auto text-violet" />
              <p className="font-bold text-[17px] mt-3">
                {file ? file.name : 'Drop a CSV file here, or click to browse'}
              </p>
              <p className="text-mute text-[14px]">UTF-8 CSV · up to 500 rows · company must already exist</p>
              <input
                ref={input}
                type="file"
                accept=".csv"
                hidden
                onChange={(e) => { setFile(e.target.files?.[0] ?? null); setRes(null); }}
              />
            </div>

            {err && (
              <div role="alert" className="mt-4 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">
                {err}
              </div>
            )}

            <div className="flex gap-3 mt-5">
              <Button variant="secondary" disabled={!file} loading={busy} onClick={() => runCsv(true)}>
                Validate File
              </Button>
              <Button disabled={!file || !res || res.valid === 0 || !res.dryRun} loading={busy} onClick={() => runCsv(false)}>
                Import {res?.valid ?? 0} Valid Row(s)
              </Button>
            </div>
          </Card>

          {res && (
            <Card padded={false} className="overflow-hidden">
              <div className="p-5 border-b border-line flex flex-wrap gap-3 items-center">
                <h3 className="font-bold text-[17px]">{res.dryRun ? 'Validation Result' : 'Import Complete'}</h3>
                <Badge tone="aqua">{res.valid} valid</Badge>
                <Badge tone="coral">{res.total - res.valid} with errors</Badge>
                {!res.dryRun && <Badge tone="lime">{res.created} created</Badge>}
              </div>
              <div className="overflow-x-auto max-h-[420px]">
                <table className="tbl w-full min-w-[640px]">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Title</th>
                      <th>Company</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {res.rows.map((r) => (
                      <tr key={r.row}>
                        <td>{r.row}</td>
                        <td className="font-semibold">{r.title || '—'}</td>
                        <td>{r.company}</td>
                        <td>
                          {r.errors.length ? (
                            <span className="flex items-start gap-2 text-[#9e2f1b]">
                              <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
                              {r.errors.join('; ')}
                            </span>
                          ) : (
                            <span className="flex items-center gap-2 text-[#0e7a7c]">
                              <CheckCircle2 className="w-4 h-4" />
                              OK
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
