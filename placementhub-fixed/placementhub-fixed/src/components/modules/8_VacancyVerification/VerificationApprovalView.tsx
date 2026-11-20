import { useState } from 'react';
import { CheckCircle2, Undo2, ExternalLink, ShieldAlert, AlertTriangle, ShieldCheck, Clock, MapPin, Building2 } from 'lucide-react';
import { api, ApiError } from '../../../lib/api';
import { useUI } from '../../../context/UIContext';
import { Badge, Button, Card, Empty, ErrorNote, Field, Modal, PageHeader, StatusBadge, TextArea, useFetch } from '../../ui/kit';
import { fmtDate, fmtDateTime } from '../../../lib/format';
import type { Page, Row } from '../../../types';
import { motion } from 'motion/react';

export default function VerificationApprovalView() {
  const { toast } = useUI();
  const q = useFetch<Page>('/api/vacancies?status=Pending Verification&pageSize=200');
  const h = useFetch<{ items: Row[] }>('/api/vacancy-verifications');
  const [sel, setSel] = useState<{ v: Row; mode: 'approve' | 'return' } | null>(null);
  const [note, setNote] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const go = async () => {
    setBusy(true);
    setErr('');
    try {
      await api.post(`/api/vacancies/${sel!.v.id}/review`, { decision: sel!.mode, note });
      toast(sel!.mode === 'approve' ? 'Vacancy approved and published to eligible students' : 'Returned to the company with your note');
      setSel(null);
      setNote('');
      q.reload();
      h.reload();
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  const getRiskTone = (level: string) => {
    switch (level) {
      case 'High Risk': return 'coral';
      case 'Requires Manual Review': return 'violet';
      case 'Medium Risk': return 'indigo';
      default: return 'lime';
    }
  };

  return (
    <div className="space-y-7">
      <PageHeader
        title="Vacancy Verification & Approval"
        subtitle="Review compensation, eligibility, verified ATS source links, and automated anti-scam indicators before a vacancy becomes visible to students."
      />

      {q.error ? (
        <ErrorNote message={q.error} onRetry={q.reload} />
      ) : !q.data?.items.length ? (
        <Empty
          title="Nothing waiting for review"
          text="All collected and submitted vacancies have been verified. Run the Aggregator Pipeline or import spreadsheets to review new opportunities."
        />
      ) : (
        <div className="grid xl:grid-cols-2 gap-5">
          {q.data.items.map((v, i) => (
            <motion.div
              key={v.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Card hover className="h-full flex flex-col space-y-4">
                {/* Header & Compensation */}
                <div className="flex justify-between items-start gap-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="font-extrabold text-[19px]">{v.title}</h3>
                    </div>
                    <p className="text-mute flex items-center gap-1.5 text-[14px]">
                      <Building2 className="w-4 h-4 text-violet shrink-0" />
                      <span className="font-semibold text-ink">{v.companyName}</span>
                      <span>·</span>
                      <span>{v.jobType}</span>
                      {v.workMode && <span>· {v.workMode}</span>}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-num font-extrabold text-[26px] text-indigo leading-none">
                      {v.ctcLpa}
                      <span className="text-[13px] text-mute font-normal"> LPA</span>
                    </p>
                    {v.stipendPerMonth ? (
                      <p className="text-[12px] text-mute font-medium mt-1">₹{v.stipendPerMonth.toLocaleString()}/mo</p>
                    ) : null}
                  </div>
                </div>

                {/* Badges row: Risk rating, source & origin link */}
                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-line/60">
                  <Badge tone={getRiskTone(v.riskLevel || 'Low Risk')}>
                    {v.riskLevel === 'High Risk' ? <ShieldAlert className="w-3.5 h-3.5 mr-1" /> : <ShieldCheck className="w-3.5 h-3.5 mr-1" />}
                    {v.riskLevel || 'Low Risk'}
                  </Badge>

                  {v.source && (
                    <Badge tone="indigo">
                      {v.source}
                    </Badge>
                  )}

                  {v.sourceUrl && (
                    <a
                      href={v.sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-indigo hover:underline ml-auto"
                    >
                      <ExternalLink className="w-3.5 h-3.5" /> Source Link
                    </a>
                  )}
                </div>

                {/* Risk Flag Alert Box if present */}
                {v.riskFlags && v.riskFlags.length > 0 && (
                  <div className="rounded-xl bg-coral/10 border border-coral/30 p-3 text-[13px] text-[#9e2f1b] space-y-1">
                    <div className="font-bold flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      Automated Scam Screener Flags:
                    </div>
                    <ul className="list-disc list-inside space-y-0.5 text-[12.5px]">
                      {v.riskFlags.map((flag: string, fIdx: number) => (
                        <li key={fIdx}>{flag}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Eligibility Details */}
                <div className="grid grid-cols-2 gap-3 text-[13.5px] bg-canvas/60 p-3 rounded-xl border border-line/60">
                  <div>
                    <p className="text-[11.5px] uppercase font-semibold text-mute">Eligibility Cutoffs</p>
                    <p className="font-medium mt-0.5">CGPA ≥ {v.minCgpa} · ≤ {v.maxBacklogs} backlogs</p>
                  </div>
                  <div>
                    <p className="text-[11.5px] uppercase font-semibold text-mute">Application Deadline</p>
                    <p className="font-medium mt-0.5">{fmtDate(v.applicationDeadline)}</p>
                  </div>
                  <div className="col-span-2 pt-1">
                    <p className="text-[11.5px] uppercase font-semibold text-mute mb-1">Eligible Departments</p>
                    <div className="flex gap-1.5 flex-wrap">
                      {(v.eligibleDepartments || []).map((d: string) => (
                        <Badge key={d} tone="violet">{d}</Badge>
                      ))}
                      {!(v.eligibleDepartments || []).length && (
                        <Badge tone="coral">No departments specified</Badge>
                      )}
                    </div>
                  </div>
                </div>

                {/* Job Description */}
                {v.description && (
                  <p className="text-[13.5px] text-ink/80 line-clamp-3 leading-relaxed">
                    {v.description}
                  </p>
                )}

                {/* Actions */}
                <div className="flex gap-3 mt-auto pt-4 border-t border-line">
                  <Button
                    variant="success"
                    onClick={() => { setSel({ v, mode: 'approve' }); setErr(''); }}
                    className="flex-1"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Approve & Publish to Students
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => { setSel({ v, mode: 'return' }); setErr(''); }}
                  >
                    <Undo2 className="w-4 h-4" />
                    Return
                  </Button>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {/* Decision History */}
      <Card padded={false} className="overflow-hidden">
        <div className="p-5 border-b border-line">
          <h3 className="font-bold text-[17px]">Institutional Verification Audit Trail</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="tbl w-full min-w-[640px]">
            <thead>
              <tr>
                <th>Vacancy</th>
                <th>Decision</th>
                <th>Reviewer</th>
                <th>Note / Justification</th>
                <th>Reviewed At</th>
              </tr>
            </thead>
            <tbody>
              {h.data?.items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <p className="font-semibold">{r.vacancyTitle}</p>
                    <p className="text-[13px] text-mute">{r.companyName}</p>
                  </td>
                  <td>
                    <StatusBadge value={r.decision === 'Approved' ? 'Approved' : 'Draft'} />
                    <span className="text-[13px] text-mute ml-1">{r.decision}</span>
                  </td>
                  <td>{r.reviewerName}</td>
                  <td className="max-w-[280px] truncate">{r.note || '—'}</td>
                  <td className="text-mute">{fmtDateTime(r.createdAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!h.data?.items.length && (
            <p className="text-center text-mute py-8">No verification decisions recorded yet.</p>
          )}
        </div>
      </Card>

      {/* Decision Modal */}
      <Modal
        open={!!sel}
        onClose={() => setSel(null)}
        title={sel?.mode === 'approve' ? 'Approve & Publish Vacancy' : 'Return Vacancy for Changes'}
        subtitle={sel?.v.title}
        width="max-w-lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setSel(null)}>Cancel</Button>
            <Button
              loading={busy}
              variant={sel?.mode === 'approve' ? 'primary' : 'danger'}
              onClick={go}
            >
              {sel?.mode === 'approve' ? 'Confirm Approval' : 'Return Vacancy'}
            </Button>
          </>
        }
      >
        {err && (
          <div role="alert" className="mb-4 rounded-xl bg-coral/10 border border-coral/30 text-[#9e2f1b] px-4 py-3 text-[14px]">
            {err}
          </div>
        )}
        <p className="text-mute text-[14px] mb-4">
          {sel?.mode === 'approve'
            ? 'Approving this vacancy will publish it immediately to all eligible students matching the CGPA and department criteria.'
            : 'Returning this vacancy will send a notification to the recruiter or author requesting modifications.'}
        </p>
        <Field label={sel?.mode === 'return' ? 'Reason for returning / required adjustments' : 'Audit Note (optional)'} required={sel?.mode === 'return'}>
          <TextArea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={sel?.mode === 'return' ? 'Specify what details need correction...' : 'e.g., Verified company credentials and salary terms'}
          />
        </Field>
      </Modal>
    </div>
  );
}
