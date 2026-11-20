import { useState } from 'react';
import { CheckCircle2, Copy, Download, Check } from 'lucide-react';
import { Button, Modal, downloadBlob } from '../ui/kit';

export interface Credentials { loginId: string; temporaryPassword: string; role: string; roleLabel: string; department: string | null; company?: string | null; status: string; fullName: string }

export function CredentialsModal({ cred, onClose }: { cred: Credentials | null; onClose: () => void }) {
  const [copied, setCopied] = useState('');
  if (!cred) return null;
  const copy = async (k: string, v: string) => { await navigator.clipboard.writeText(v).catch(() => {}); setCopied(k); setTimeout(() => setCopied(''), 1600); };
  const download = () => downloadBlob(new Blob([
    `PlacementHub – account credentials (ONE-TIME DOCUMENT)\n\nName: ${cred.fullName}\nLogin ID: ${cred.loginId}\nTemporary password: ${cred.temporaryPassword}\nRole: ${cred.roleLabel}\nDepartment: ${cred.department ?? '—'}\n${cred.company ? `Company: ${cred.company}\n` : ''}Status: ${cred.status}\n\nYou must change this password at first sign-in. Delete this file after use.\n`], { type: 'text/plain' }), `credentials_${cred.loginId.split('@')[0]}.txt`);
  const Row = ({ k, label, value, mono }: { k?: string; label: string; value: string; mono?: boolean }) => (
    <div className="flex items-center justify-between gap-3 py-3.5 border-b border-line last:border-0">
      <div className="min-w-0"><p className="text-[12.5px] font-semibold uppercase tracking-wide text-mute">{label}</p><p className={`text-[16px] font-semibold truncate ${mono ? 'font-mono tracking-wide' : ''}`}>{value}</p></div>
      {k && <Button size="sm" variant="secondary" onClick={() => copy(k, value)}>{copied === k ? <Check className="w-4 h-4 text-aqua" /> : <Copy className="w-4 h-4" />}{copied === k ? 'Copied' : 'Copy'}</Button>}
    </div>
  );
  return (
    <Modal open onClose={onClose} title="Account created successfully" subtitle={cred.fullName} width="max-w-xl"
      footer={<><Button variant="secondary" onClick={download}><Download className="w-4 h-4" />Download credentials</Button><Button onClick={onClose}>I have saved them</Button></>}>
      <div className="flex items-center gap-3 rounded-2xl bg-aqua/12 text-[#0e6f71] px-4 py-3 mb-4"><CheckCircle2 className="w-5 h-5 shrink-0" /><span className="text-[14px]">The temporary password is shown <b>only once</b>. Only its secure hash is stored; it cannot be retrieved later.</span></div>
      <Row k="id" label="Login name" value={cred.loginId} />
      <Row k="pw" label="Temporary password" value={cred.temporaryPassword} mono />
      <Row label="Assigned role" value={cred.roleLabel} />
      <Row label="Department" value={cred.department ?? '—'} />
      {cred.company && <Row label="Company" value={cred.company} />}
      <Row label="Account status" value={cred.status === 'active' ? 'Active – password change required at first login' : cred.status} />
    </Modal>
  );
}
