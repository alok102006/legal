import React, { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Badge, Button, ErrorState, Field, Input, Select, Skeleton } from '@/ui/primitives';
import { ConfirmDialog, Modal } from '@/ui/overlays';
import { formatDateTime, titleCase } from '@/lib/utils';
import { MSME_OPTIONS } from '@/features/org/api';
import { useDeleteVendor, useRecheckVendor, useUpdateVendor, useVendor, type VendorDetail } from './api';
import { VendorRiskBadge, VerificationCard, ago, viewFromVendor } from './components';
import { SuppliersPanel } from './SuppliersPanel';

const EditDialog: React.FC<{ vendor: VendorDetail; open: boolean; onClose: () => void }> = ({ vendor, open, onClose }) => {
  const update = useUpdateVendor(vendor.id);
  const [f, setF] = useState({ name: vendor.name, gstin: vendor.gstin ?? '', pan: vendor.pan ?? '', udyam_number: vendor.udyam_number ?? '', msme_category: vendor.msme_category ?? '' });
  const err = update.isError ? toFriendlyError(update.error).message : null;
  return (
    <Modal open={open} onOpenChange={(o) => { if (!o) onClose(); }} title="Edit supplier details" description="We re-run the checks when you save."
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button loading={update.isPending} disabled={f.name.trim().length < 2} onClick={() => update.mutate(
          { name: f.name.trim(), gstin: f.gstin, pan: f.pan, udyam_number: f.udyam_number, msme_category: f.msme_category || undefined },
          { onSuccess: () => { toast.success('Saved and re-checked'); onClose(); } })}>Save</Button>
      </>}>
      <div className="space-y-4">
        {err && <ErrorState message={err} />}
        <Field label="Name" required>{({ id }) => <Input id={id} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="GSTIN">{({ id }) => <Input id={id} className="font-mono uppercase" value={f.gstin} onChange={(e) => setF({ ...f, gstin: e.target.value.toUpperCase() })} />}</Field>
          <Field label="PAN">{({ id }) => <Input id={id} className="font-mono uppercase" value={f.pan} onChange={(e) => setF({ ...f, pan: e.target.value.toUpperCase() })} />}</Field>
          <Field label="MSME status">{({ id }) => (
            <Select id={id} value={f.msme_category} onChange={(e) => setF({ ...f, msme_category: e.target.value })}>
              <option value="">Not set</option>
              {MSME_OPTIONS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </Select>)}
          </Field>
          <Field label="Udyam number">{({ id }) => <Input id={id} className="font-mono uppercase" value={f.udyam_number} onChange={(e) => setF({ ...f, udyam_number: e.target.value.toUpperCase() })} placeholder="UDYAM-MH-26-0012345" />}</Field>
        </div>
      </div>
    </Modal>
  );
};

export const VendorPage: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: v, isLoading, isError, error, refetch } = useVendor(id);
  const recheck = useRecheckVendor(id ?? '');
  const del = useDeleteVendor();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const back = <Link to="/vendors" className="inline-flex items-center gap-1 text-sm font-medium text-ink-2 hover:text-ink"><ArrowLeft className="h-4 w-4" aria-hidden />Check desk</Link>;
  const wrap = (children: React.ReactNode) => (
    <div className="relative h-full overflow-hidden">
      <SuppliersPanel activeId={id} />
      <div className="h-full overflow-y-auto"><div className="mx-auto w-full max-w-2xl px-4 pb-20 pt-16 sm:px-6">{children}</div></div>
    </div>
  );

  if (isLoading) return wrap(<div className="space-y-4"><Skeleton className="h-6 w-28" /><Skeleton className="h-10 w-1/2" /><Skeleton className="h-80 w-full" /></div>);
  if (isError || !v) {
    const fe = toFriendlyError(error);
    return wrap(<div className="space-y-4">{back}<ErrorState title={fe.status === 404 ? 'Supplier not found' : 'Could not load this supplier'} message={fe.message} onRetry={fe.status === 404 ? undefined : () => refetch()} /></div>);
  }

  const doRecheck = () => recheck.mutate(undefined, { onSuccess: () => toast.success('Checked again'), onError: (e) => toast.error(toFriendlyError(e).message) });

  return wrap(
    <>
      <div className="mb-5">{back}</div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="break-words font-display text-3xl leading-tight text-ink sm:text-4xl">{v.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <VendorRiskBadge risk={v.risk_level} />
            {v.msme_category && v.msme_category !== 'unknown' && <Badge>MSME: {titleCase(v.msme_category)}</Badge>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>Edit</Button>
          <Button size="sm" variant="ghost" className="!h-9 !w-9 !rounded-lg !px-0" aria-label="Delete supplier" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" aria-hidden /></Button>
        </div>
      </div>

      <VerificationCard view={viewFromVendor(v)} animate={false} onRetryRegistry={doRecheck} retrying={recheck.isPending}
        actions={<Button size="sm" icon={<RefreshCw className="h-4 w-4" aria-hidden />} loading={recheck.isPending} onClick={doRecheck}>Re-check</Button>} />

      <section className="mt-10" aria-labelledby="history">
        <h2 id="history" className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">History of checks</h2>
        {v.history.length === 0 ? <p className="text-sm text-ink-2">Only the latest check is stored for this supplier. Re-check to start a history.</p> : (
          <ol className="divide-y divide-line overflow-hidden rounded-2xl bg-surface-2">
            {v.history.map((h, i) => (
              <li key={h.at + i} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
                <span className="w-44 shrink-0 text-sm text-ink" title={formatDateTime(h.at)}>{formatDateTime(h.at)}<span className="ml-2 text-xs text-ink-3">{ago(h.at)}</span></span>
                <VendorRiskBadge risk={h.risk_level} short />
                <span className="min-w-0 flex-1 truncate text-sm text-ink-2">
                  {h.registry_source === 'live' ? `Live registry${h.registry_status ? `: ${h.registry_status}` : ''}` : h.registry_source === 'sample' ? 'Sample registry' : 'Offline checks only'}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      {editing && <EditDialog vendor={v} open onClose={() => setEditing(false)} />}
      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} danger loading={del.isPending} title="Delete this supplier?" description={v.name} confirmLabel="Delete"
        onConfirm={() => del.mutate(v.id, { onSuccess: () => { toast.success('Supplier deleted'); navigate('/vendors'); }, onError: (e) => toast.error(toFriendlyError(e).message) })} />
    </>,
  );
};
