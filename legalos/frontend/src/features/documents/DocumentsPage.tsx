/** Documents workspace: a chat over the company's own papers.
 *  Centre: one conversation. Right (on demand, via the floating button): the library of chats, collections and documents.
 *  The cited passage opens as a sheet over everything. */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, BookOpen, ChevronDown, FolderOpen, Library, Loader2, MessageSquarePlus, Pencil, Plus, Sparkles, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, Dropzone, ErrorState, Field, Input, Select, Skeleton } from '@/ui/primitives';
import { ConfirmDialog, Modal } from '@/ui/overlays';
import { PanelLabel, SidePanel, closeSidePanel } from '@/ui/sidepanel';
import { useNewParam } from '@/ui/workspace';
import { cn } from '@/lib/utils';
import { useLoadSample } from '@/features/samples/api';
import {
  DOC_CATEGORIES, streamAsk, useCollections, useConversation, useConversations, useCreateConversation, useDeleteConversation,
  useDocuments, useSuggestions, useUpdateConversation, useUploadDocument, type Conversation, type DocListItem, type Turn,
} from './api';
import { AssistantMessage, Composer, PendingMessage, SourcePanel, UserMessage } from './components';

const ALL = '__all__';
const scopeLabel = (c: string | null) => c ?? 'All documents';

/* ------------------------------------------------------------------ upload */

const UploadDialog: React.FC<{ open: boolean; onOpenChange: (o: boolean) => void; collections: string[]; initial?: string | null }> = ({ open, onOpenChange, collections, initial }) => {
  const upload = useUploadDocument();
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState(initial ?? '');
  const [custom, setCustom] = useState('');
  useEffect(() => { if (open) setCategory(initial ?? ''); }, [open, initial]);
  const options = Array.from(new Set([...collections, ...DOC_CATEGORIES]));
  const chosen = category === '__new__' ? custom.trim() : category;
  const err = upload.isError ? toFriendlyError(upload.error).message : null;
  return (
    <Modal open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) { setFile(null); upload.reset(); } }} title="Add a document" description="It is read, indexed for questions, and summarised. Scans work too.">
      <div className="space-y-4">
        <Dropzone accept=".pdf,.docx,.txt,.csv,.xlsx" file={file} onFile={(f) => { setFile(f); upload.reset(); }} disabled={upload.isPending} hint="PDF, Word, Excel, CSV or text · up to 15 MB" />
        <Field label="Collection" hint="Groups documents so you can ask questions within one set, e.g. HR or Finance.">
          {({ id }) => <Select id={id} value={category} onChange={(e) => setCategory(e.target.value)}><option value="">General</option>{options.map((c) => <option key={c} value={c}>{c}</option>)}<option value="__new__">New collection…</option></Select>}
        </Field>
        {category === '__new__' && <Field label="Collection name">{({ id }) => <Input id={id} value={custom} onChange={(e) => setCustom(e.target.value)} maxLength={80} placeholder="e.g. Board minutes" />}</Field>}
        {err && <ErrorState title="Couldn't add this document" message={err} />}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button icon={<Upload className="h-4 w-4" aria-hidden />} loading={upload.isPending} disabled={!file || (category === '__new__' && !custom.trim())}
            onClick={() => file && upload.mutate({ file, category: chosen || undefined }, { onSuccess: () => { toast.success('Added. Reading it now — you can ask about it in a moment.'); onOpenChange(false); } })}>Add document</Button>
        </div>
      </div>
    </Modal>
  );
};

/* ------------------------------------------------------------------ library (right panel) */

/** On small screens the panel is an overlay; close it after the reader has picked something. */
function closePanelOnMobile() {
  try { if (window.matchMedia('(max-width: 767px)').matches) closeSidePanel('documents-library'); } catch { /* ignore */ }
}

const rowBase = 'flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left';

const DocRow: React.FC<{ d: DocListItem }> = ({ d }) => {
  const busy = d.status === 'processing' || (d.status === 'ready' && d.review_state === 'pending');
  return (
    <Link to={`/documents/${d.id}`} onClick={closePanelOnMobile} className={cn(rowBase, 'hover:bg-surface-2')} title={d.title}>
      {d.status === 'failed' ? <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-critical-ink" aria-label="Failed" />
        : busy ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-ink-3" aria-label="Processing" />
        : <span className="h-2 w-2 shrink-0 rounded-full bg-good" aria-label="Ready" />}
      <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium text-ink">{d.title}</span>
    </Link>
  );
};

const ChatRow: React.FC<{ c: Conversation; active: boolean; onRename: () => void; onDelete: () => void }> = ({ c, active, onRename, onDelete }) => (
  <div className={cn('group flex items-center rounded-xl pr-1', active ? 'bg-surface-2' : 'hover:bg-surface-2')}>
    <Link to={`/documents/c/${c.id}`} onClick={closePanelOnMobile} className="min-w-0 flex-1 truncate px-2.5 py-2 text-[13.5px] font-medium text-ink" title={c.title} aria-current={active ? 'page' : undefined}>{c.title}</Link>
    <span className={cn('flex shrink-0 text-ink-3 opacity-0 focus-within:opacity-100 group-hover:opacity-100 max-md:opacity-100', active && 'opacity-100')}>
      <button onClick={onRename} className="rounded-lg p-1.5 hover:bg-surface hover:text-ink" aria-label={`Rename chat ${c.title}`}><Pencil className="h-3.5 w-3.5" aria-hidden /></button>
      <button onClick={onDelete} className="rounded-lg p-1.5 hover:bg-surface hover:text-ink" aria-label={`Delete chat ${c.title}`}><Trash2 className="h-3.5 w-3.5" aria-hidden /></button>
    </span>
  </div>
);

const ScopeRow: React.FC<{ active: boolean; icon: React.ReactNode; label: string; count: number; onClick: () => void }> = ({ active, icon, label, count, onClick }) => (
  <button onClick={onClick} aria-pressed={active} className={cn(rowBase, active ? 'bg-surface-2' : 'hover:bg-surface-2')}>
    <span className="shrink-0 text-ink-3" aria-hidden>{icon}</span>
    <span className={cn('min-w-0 flex-1 truncate text-[13.5px] text-ink', active ? 'font-semibold' : 'font-medium')}>{label}</span>
    <span className="text-xs text-ink-3">{count}</span>
  </button>
);

const LibraryPanel: React.FC<{
  activeConv?: string; scope: string | null; onScope: (c: string | null) => void; onUpload: () => void; onNewChat: () => void;
}> = ({ activeConv, scope, onScope, onUpload, onNewChat }) => {
  const collections = useCollections();
  const docs = useDocuments(scope);
  const convs = useConversations();
  const rename = useUpdateConversation();
  const del = useDeleteConversation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState<Conversation | null>(null);
  const [title, setTitle] = useState('');
  const [deleting, setDeleting] = useState<Conversation | null>(null);
  const total = (collections.data ?? []).reduce((n, c) => n + c.count, 0);
  // labels collapse to icons on phones, and while the panel is open (the buttons would sit on the panel header)
  const label = (text: string) => <span className={cn('max-sm:hidden', open && 'md:hidden')}>{text}</span>;
  const compact = 'max-sm:w-10 max-sm:px-0' + (open ? ' md:w-10 md:px-0' : '');

  const actions = (
    <>
      <Button className={cn('rounded-full', compact)} variant="secondary" aria-label="Add a document" title="Add a document" icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => { closePanelOnMobile(); onUpload(); }}>{label('Add a document')}</Button>
      <Button className={cn('rounded-full', compact)} aria-label="New chat" title="New chat" icon={<MessageSquarePlus className="h-4 w-4" aria-hidden />} onClick={() => { closePanelOnMobile(); onNewChat(); }}>{label('New chat')}</Button>
    </>
  );

  return (
    <>
      <SidePanel storageKey="documents-library" title="Library" icon={Library} count={convs.data?.length} actions={actions} onOpenChange={setOpen}>
        <PanelLabel>Chats</PanelLabel>
        {convs.isLoading && <Skeleton className="h-10" />}
        {convs.data && convs.data.length === 0 && <p className="px-2.5 text-xs text-ink-3">Your questions will be kept here.</p>}
        {convs.data && convs.data.length > 0 && (
          <ul className="space-y-0.5">{convs.data.map((c) => <li key={c.id}><ChatRow c={c} active={c.id === activeConv} onRename={() => { setRenaming(c); setTitle(c.title); }} onDelete={() => setDeleting(c)} /></li>)}</ul>
        )}

        <PanelLabel>Collections</PanelLabel>
        {collections.isLoading && <Skeleton className="h-16" />}
        {collections.data && (
          <ul className="space-y-0.5">
            <li><ScopeRow active={scope === null} icon={<BookOpen className="h-4 w-4" />} label="All documents" count={total} onClick={() => { onScope(null); closePanelOnMobile(); }} /></li>
            {collections.data.map((c) => (
              <li key={c.name}><ScopeRow active={scope === c.name} icon={<FolderOpen className="h-4 w-4" />} label={c.name} count={c.count} onClick={() => { onScope(c.name); closePanelOnMobile(); }} /></li>
            ))}
          </ul>
        )}

        <PanelLabel>{scope ? `In ${scope}` : 'Documents'}</PanelLabel>
        {docs.isLoading && <Skeleton className="h-10" />}
        {docs.data && docs.data.length === 0 && <p className="px-2.5 text-xs text-ink-3">Nothing here yet.</p>}
        {docs.data && docs.data.length > 0 && <ul className="space-y-0.5">{docs.data.map((d) => <li key={d.id}><DocRow d={d} /></li>)}</ul>}
      </SidePanel>

      <Modal open={!!renaming} onOpenChange={(o) => !o && setRenaming(null)} title="Rename chat"
        footer={<><Button variant="secondary" onClick={() => setRenaming(null)}>Cancel</Button><Button loading={rename.isPending} disabled={!title.trim()} onClick={() => renaming && rename.mutate({ id: renaming.id, title: title.trim() }, { onSuccess: () => setRenaming(null), onError: (e) => toast.error(toFriendlyError(e).message) })}>Save</Button></>}>
        <Field label="Title">{({ id }) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} autoFocus />}</Field>
      </Modal>
      <ConfirmDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)} danger title="Delete this chat?" description="The questions and answers in it will be removed. Your documents stay." confirmLabel="Delete" loading={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id, { onSuccess: () => { if (deleting.id === activeConv) navigate('/documents'); setDeleting(null); }, onError: (e) => toast.error(toFriendlyError(e).message) })} />
    </>
  );
};

/* ------------------------------------------------------------------ conversation */

interface Pending { question: string; stage: 'sending' | 'searching' | 'writing'; text: string }

const Thread: React.FC<{ turns: Turn[]; pending: Pending | null; error: string | null; onOpen: (turn: Turn, marker: string) => void }> = ({ turns, pending, error, onOpen }) => {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }); }, [turns.length, pending?.text, pending?.stage, error]);
  return (
    <div className="mx-auto w-full max-w-3xl space-y-7 px-4 py-6">
      {turns.map((t) => t.role === 'user' ? <UserMessage key={t.id} text={t.content} /> : <AssistantMessage key={t.id} turn={t} onOpen={(m) => onOpen(t, m)} />)}
      {pending && <><UserMessage text={pending.question} /><PendingMessage stage={pending.stage} text={pending.text} /></>}
      {error && <ErrorState title="Couldn't answer that" message={error} />}
      <div ref={endRef} />
    </div>
  );
};

const EmptyThread: React.FC<{ scope: string | null; hasDocs: boolean; onAsk: (q: string) => void; onUpload: () => void; onSample: () => void; sampleLoading: boolean }> = ({ scope, hasDocs, onAsk, onUpload, onSample, sampleLoading }) => {
  const suggestions = useSuggestions(scope, hasDocs);
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-4 py-10 text-center">
      <span className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-2 text-ink-2 shadow-card" aria-hidden><BookOpen className="h-5 w-5" /></span>
      {hasDocs ? (
        <>
          <h2 className="font-display text-4xl text-ink">What do you want to know?</h2>
          <p className="mt-3 max-w-md text-[15px] leading-7 text-ink-2">Ask in English, Hindi or Hinglish. Every answer quotes the passage and page it came from — or says plainly when your documents don't cover it.</p>
          {suggestions.data && suggestions.data.length > 0 && (
            <ul className="mt-8 grid w-full gap-2.5 text-left sm:grid-cols-2">
              {suggestions.data.map((q) => <li key={q}><button onClick={() => onAsk(q)} className="flex w-full items-start gap-2.5 rounded-xl bg-surface-2 px-4 py-3.5 text-left text-sm leading-6 text-ink-2 transition-shadow hover:bg-surface hover:text-ink hover:shadow-raised"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-ink-3" aria-hidden />{q}</button></li>)}
            </ul>
          )}
        </>
      ) : (
        <>
          <h2 className="font-display text-4xl text-ink">Your documents, answerable</h2>
          <p className="mt-3 max-w-md text-[15px] leading-7 text-ink-2">Add your HR policy, licences, agreements and board records. Then ask questions like “what notice period did we agree?” and get the answer with the page.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-2">
            <Button size="lg" icon={<Upload className="h-4 w-4" aria-hidden />} onClick={onUpload}>Add a document</Button>
            <Button size="lg" variant="secondary" icon={<Sparkles className="h-4 w-4" aria-hidden />} onClick={onSample} loading={sampleLoading}>Try with a sample handbook</Button>
          </div>
        </>
      )}
    </div>
  );
};

/* ------------------------------------------------------------------ page */

export const DocumentsPage: React.FC = () => {
  const { convId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [uploadOpen, setUploadOpen] = useNewParam();
  const [askFocus] = useNewParam('ask');
  const [scope, setScope] = useState<string | null>(null);          // collection for the NEXT chat
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<{ turn: Turn; marker: string } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const collections = useCollections();
  const conv = useConversation(convId);
  const create = useCreateConversation();
  const sample = useLoadSample();
  const hasDocs = (collections.data ?? []).some((c) => c.count > 0);
  const names = (collections.data ?? []).map((c) => c.name);
  const activeScope = convId ? (conv.data?.collection ?? null) : scope;

  useEffect(() => { setPending(null); setError(null); setSource(null); abortRef.current?.abort(); }, [convId]);
  useEffect(() => () => abortRef.current?.abort(), []);

  const send = useCallback(async (id: string, question: string) => {
    const ac = new AbortController();
    abortRef.current = ac;
    setError(null);
    setPending({ question, stage: 'sending', text: '' });
    try {
      await streamAsk(id, question, (e) => {
        if (e.kind === 'stage') setPending((p) => p && { ...p, stage: e.stage });
        else if (e.kind === 'delta') setPending((p) => p && { ...p, text: p.text + e.text });
        else if (e.kind === 'error') setError(e.message);
        else if (e.kind === 'done') {
          qc.setQueryData(['conversations', id], (old: { turns: Turn[]; title: string } | undefined) => old && { ...old, turns: [...old.turns, { ...e.turn, role: 'user', id: `${e.turn.id}-q`, content: question, citations: [], sources: [] }, e.turn] });
          qc.invalidateQueries({ queryKey: ['conversations'] });
        }
      }, ac.signal);
    } catch (err) {
      if (!ac.signal.aborted) setError(err instanceof Error ? err.message : 'Could not get an answer.');
    } finally {
      if (abortRef.current === ac) { setPending(null); abortRef.current = null; }
    }
  }, [qc]);

  const ask = useCallback((question: string) => {
    if (convId) { void send(convId, question); return; }
    // a brand-new chat: create it, open it, and hand the question over so it is sent once the route has settled
    create.mutate({ collection: scope }, {
      onSuccess: (c) => navigate(`/documents/c/${c.id}`, { state: { ask: question } }),
      onError: (e) => toast.error(toFriendlyError(e).message),
    });
  }, [convId, scope, create, navigate, send]);

  // a question handed over from a document page ("Ask about this") is asked as soon as the chat is open
  const location = useLocation();
  const handedOver = (location.state as { ask?: string } | null)?.ask;
  useEffect(() => {
    if (convId && handedOver && conv.data && !pending) {
      navigate(location.pathname, { replace: true, state: null });
      void send(convId, handedOver);
    }
  }, [convId, handedOver, conv.data, pending, navigate, location.pathname, send]);

  const stop = () => { abortRef.current?.abort(); setPending(null); };
  const loadSample = () => sample.mutate('document', { onSuccess: () => toast.success('Sample handbook added. Reading it now.'), onError: (e) => toast.error(toFriendlyError(e).message) });

  const scopePicker = convId
    ? <span>Asking <strong className="font-medium text-ink-2">{scopeLabel(activeScope)}</strong></span>
    : (
      <label className="flex items-center gap-1">
        <span>Asking</span>
        <span className="relative">
          <select value={scope ?? ALL} onChange={(e) => setScope(e.target.value === ALL ? null : e.target.value)} aria-label="Which documents to ask" className="appearance-none rounded-md border border-transparent bg-transparent py-0.5 pl-1 pr-5 font-medium text-ink-2 hover:border-line hover:bg-surface">
            <option value={ALL}>All documents</option>{names.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <ChevronDown className="pointer-events-none absolute right-1 top-1/2 h-3 w-3 -translate-y-1/2" aria-hidden />
        </span>
      </label>
    );

  return (
    <div className="relative h-full overflow-hidden">
      <LibraryPanel activeConv={convId} scope={scope} onScope={(c) => { setScope(c); if (convId) navigate('/documents'); }}
        onUpload={() => setUploadOpen(true)} onNewChat={() => navigate('/documents')} />

      <section className="flex h-full min-w-0 flex-col" aria-label="Conversation">
        <div className="flex h-[68px] shrink-0 items-center px-5 pr-40 sm:pr-[22rem]">
          {convId && <h1 className="truncate text-[13px] font-medium text-ink-2">{conv.data?.title ?? '…'}</h1>}
        </div>

        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          {convId && conv.isLoading && <div className="mx-auto w-full max-w-3xl space-y-4 px-4 py-6"><Skeleton className="ml-auto h-10 w-1/2" /><Skeleton className="h-24" /></div>}
          {convId && conv.isError && <div className="mx-auto w-full max-w-3xl px-4 py-6"><ErrorState title="Couldn't open this chat" message={toFriendlyError(conv.error).message} onRetry={() => conv.refetch()} /></div>}
          {convId && conv.data && (conv.data.turns.length > 0 || pending || error) && <Thread turns={conv.data.turns} pending={pending} error={error} onOpen={(turn, marker) => setSource({ turn, marker })} />}
          {((!convId && !pending) || (conv.data && conv.data.turns.length === 0 && !pending && !error)) && (
            <EmptyThread scope={activeScope} hasDocs={hasDocs} onAsk={ask} onUpload={() => setUploadOpen(true)} onSample={loadSample} sampleLoading={sample.isPending} />
          )}
          {!convId && pending && <Thread turns={[]} pending={pending} error={error} onOpen={() => undefined} />}
        </div>

        <div className="px-3 pb-4 pt-2 sm:px-6">
          <Composer onSend={ask} onStop={stop} busy={!!pending || create.isPending} disabled={!hasDocs && !collections.isLoading} autoFocus={askFocus || !!convId}
            placeholder={hasDocs ? undefined : 'Add a document first, then ask about it'} scope={hasDocs ? scopePicker : undefined} />
        </div>
      </section>

      <SourcePanel turn={source?.turn ?? null} marker={source?.marker ?? null} onClose={() => setSource(null)} />
      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} collections={names} initial={activeScope} />
    </div>
  );
};
