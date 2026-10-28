import React, { useMemo, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { AlertTriangle, History, Landmark, Loader2, PenLine, Plus, Search, ScanSearch, Sparkles, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { useSession } from '@/lib/auth/session';
import { useLoadSample } from '@/features/samples/api';
import { PhotoDropzone } from '@/features/shared/PhotoDropzone';
import { AiDisclaimer, Button, EmptyState, ErrorState, Field, Input, SkeletonRows } from '@/ui/primitives';
import { Modal } from '@/ui/overlays';
import { SidePanel, PanelLabel, closeSidePanel } from '@/ui/sidepanel';
import { useNewParam } from '@/ui/workspace';
import { cn, formatDate } from '@/lib/utils';
import { contractTypeLabel, useContracts, useUploadContract, type ContractListItem } from './api';
import { RISK_DOT } from './components';
import { ContractView } from './ContractView';

const PANEL_KEY = 'contracts-history';
const ACCEPT = '.pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp';
const ALLOWED = ACCEPT.replace(/\./g, '').split(',');
const MAX_BYTES = 10 * 1024 * 1024;

/* ------------------------------------------------------------------ upload form (stage and dialog) */

const UploadForm: React.FC<{ onStarted?: () => void; showSample?: boolean }> = ({ onStarted, showSample }) => {
  const { org } = useSession();
  const navigate = useNavigate();
  const upload = useUploadContract();
  const sample = useLoadSample();
  const [files, setFiles] = useState<File[]>([]);
  const [party, setParty] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const err = localError ?? (upload.isError ? toFriendlyError(upload.error).message : null);

  const pick = (list: File[]) => {
    upload.reset();
    setLocalError(null);
    for (const f of list) {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
      if (!ALLOWED.includes(ext)) return setLocalError(`'.${ext}' files are not supported. Please upload a PDF, Word, text or image file.`);
      if (f.size > MAX_BYTES) return setLocalError(`${f.name} is larger than 10 MB. Try a smaller scan or split it.`);
    }
    setFiles(list);
  };
  const file = files.length > 0;

  const start = () => file && upload.mutate({ files, clientParty: party }, {
    onSuccess: (c) => { toast.success('Uploaded. Reading has started.'); onStarted?.(); navigate(`/contracts/${c.id}`); },
  });
  const loadSample = () => sample.mutate('contract', {
    onSuccess: (r) => { toast.success('Sample contract added. Reading it now.'); onStarted?.(); navigate(r.path); },
    onError: (e) => toast.error(toFriendlyError(e).message),
  });

  return (
    <form className="space-y-5" onSubmit={(e) => { e.preventDefault(); start(); }}>
      <PhotoDropzone accept={ACCEPT} files={files} onFiles={pick} disabled={upload.isPending}
        hint="PDF, Word, text, or photos of the pages (add them in order) · up to 10 MB each" />
      {file && (
        <Field label="Which party are you?" hint={`Optional. Leave blank and we will assume you are ${org?.legal_name ?? 'your company'}.`}>
          {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={party} onChange={(e) => setParty(e.target.value)} placeholder="e.g. Buyer, Tenant, or your name as written in the contract" />}
        </Field>
      )}
      {err && <ErrorState title="Couldn't upload this file" message={err} />}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="lg" loading={upload.isPending} disabled={!file} className="h-12" icon={<Upload className="h-4 w-4" aria-hidden />}>Start reading</Button>
        {showSample && (
          <button type="button" onClick={loadSample} disabled={sample.isPending}
            className="inline-flex min-h-[44px] items-center gap-1.5 rounded-lg px-2 text-sm font-medium text-ink-2 transition-colors hover:text-ink hover:underline disabled:opacity-60">
            {sample.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Sparkles className="h-4 w-4" aria-hidden />}
            Or try the sample supply agreement
          </button>
        )}
      </div>
    </form>
  );
};

const CHECKS: [React.ElementType, string, string][] = [
  [PenLine, 'Clauses that could hurt you', 'Uncapped liability, one-sided termination, penalties, lock-ins and auto-renewal, each with the exact words and page.'],
  [Landmark, 'Indian law, checked', 'MSME 45-day payment rule, stamp duty, non-competes under s.27, arbitration seat and more, with the section cited.'],
  [ScanSearch, 'What to ask for instead', 'A suggested change and ready-to-send wording for every issue, before you sign.'],
];

const UploadStage: React.FC = () => (
  <div className="h-full overflow-y-auto">
    <div className="mx-auto grid w-full max-w-6xl gap-10 px-6 pb-20 pt-20 sm:px-10 lg:grid-cols-[1.15fr_1fr] lg:gap-16 lg:pt-24 xl:px-14">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Contracts</p>
        <h1 className="mt-3 font-display text-4xl leading-[1.05] text-ink sm:text-[3.6rem]">Read it before you sign it.</h1>
        <p className="mt-4 max-w-xl text-base text-ink-2">Upload any contract. We read every clause, mark what could hurt you, and tell you what to ask for instead, in plain English.</p>
        <div className="mt-8 rounded-2xl bg-surface-2 p-4 sm:p-6">
          <UploadForm showSample />
        </div>
        <AiDisclaimer className="mt-6" />
      </div>
      <div className="lg:pt-24">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">What we check</p>
        <ul className="mt-4 space-y-3" aria-label="What we check">
          {CHECKS.map(([Icon, title, body]) => (
            <li key={title} className="flex gap-4 rounded-2xl bg-surface-2 p-4 transition-shadow hover:shadow-card">
              <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface text-ink-2 shadow-card" aria-hidden><Icon className="h-4 w-4" /></span>
              <span><span className="block text-[15px] font-semibold text-ink">{title}</span><span className="mt-0.5 block text-sm leading-relaxed text-ink-2">{body}</span></span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  </div>
);

/* ------------------------------------------------------------------ history (lives in the right side panel) */

const ContractRow: React.FC<{ c: ContractListItem; onPick: () => void }> = ({ c, onPick }) => {
  const running = c.status === 'processing' || c.status === 'queued';
  const level = c.risk_level;
  const sub = [c.counterparty_name, contractTypeLabel(c.contract_type)].filter(Boolean).join(' · ') || (c.filename ?? '');
  return (
    <NavLink
      to={`/contracts/${c.id}`}
      onClick={onPick}
      className={({ isActive }) => cn('group flex items-start gap-3 rounded-xl px-2.5 py-2 transition-colors hover:bg-surface-2', isActive && 'bg-surface-2')}
    >
      <span className="mt-1.5 flex h-3 w-3 shrink-0 items-center justify-center">
        {running ? <Loader2 className="h-3.5 w-3.5 animate-spin text-ink-3" aria-label="Reading" />
          : c.status === 'failed' ? <AlertTriangle className="h-3.5 w-3.5 text-critical-ink" aria-label="Needs retry" />
          : level ? <span className={cn('h-2.5 w-2.5 rounded-full', RISK_DOT[level])} role="img" aria-label={`${level} risk`} />
          : <span className="h-2.5 w-2.5 rounded-full bg-line-strong" aria-hidden />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13.5px] font-medium text-ink" title={c.title ?? undefined}>{c.title || c.filename || 'Contract'}</span>
        <span className="block truncate text-xs text-ink-3">{sub}</span>
        <span className="mt-0.5 block truncate text-xs text-ink-3">
          {running ? 'Reading…' : c.status === 'failed' ? 'Needs a retry' : [level && `${level[0].toUpperCase()}${level.slice(1)} risk`, formatDate(c.created_at)].filter(Boolean).join(' · ')}
        </span>
      </span>
    </NavLink>
  );
};

const ContractList: React.FC<{ onPick: () => void }> = ({ onPick }) => {
  const { data, isLoading, isError, error, refetch, isFetching } = useContracts();
  const [q, setQ] = useState('');
  const list = useMemo(() => {
    const s = q.trim().toLowerCase();
    const all = data ?? [];
    return s ? all.filter((c) => [c.title, c.counterparty_name, c.filename, contractTypeLabel(c.contract_type)].some((v) => v?.toLowerCase().includes(s))) : all;
  }, [data, q]);

  return (
    <>
      {(data?.length ?? 0) > 3 && (
        <div className="relative mb-3 px-2">
          <Search className="pointer-events-none absolute left-5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <label htmlFor="contract-search" className="sr-only">Search contracts</label>
          <Input id="contract-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search contracts" className="h-9 pl-9 text-sm" />
        </div>
      )}
      <PanelLabel>Recent</PanelLabel>
      <nav aria-label="Your contracts">
        {isLoading && <SkeletonRows rows={4} className="px-2" />}
        {isError && <ErrorState message={toFriendlyError(error).message} onRetry={() => refetch()} retrying={isFetching} />}
        {data && data.length === 0 && <EmptyState icon={<History className="h-5 w-5" />} title="No contracts yet" description="Upload one and it will be kept here." className="py-10" />}
        {data && data.length > 0 && list.length === 0 && <EmptyState title={`No contract matches “${q}”`} description="Try a different name or party." className="py-8" />}
        <ul className="space-y-0.5">{list.map((c) => <li key={c.id}><ContractRow c={c} onPick={onPick} /></li>)}</ul>
      </nav>
    </>
  );
};

/* ------------------------------------------------------------------ the room */

export const ReadingRoom: React.FC<{ selectedId?: string }> = ({ selectedId }) => {
  const [dialog, setDialog] = useNewParam();
  const { data } = useContracts();
  const closeOnPhone = () => {
    if (window.matchMedia('(max-width: 767px)').matches) closeSidePanel(PANEL_KEY);
  };
  return (
    <div className="relative h-full overflow-hidden">
      <SidePanel
        storageKey={PANEL_KEY}
        title="Your contracts"
        icon={History}
        count={data?.length}
        actions={(
          <Button icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => setDialog(true)} className="h-10 rounded-full max-sm:px-3">
            <span className="max-sm:sr-only">Upload contract</span>
          </Button>
        )}
      >
        <ContractList onPick={closeOnPhone} />
      </SidePanel>
      <div className="h-full">
        {selectedId ? <ContractView key={selectedId} id={selectedId} /> : <UploadStage />}
      </div>
      <Modal open={dialog} onOpenChange={setDialog} title="Read a contract" description="Takes about a minute. Don't upload anything you aren't allowed to share.">
        <UploadForm onStarted={() => setDialog(false)} />
      </Modal>
    </div>
  );
};
