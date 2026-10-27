import React, { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, CalendarClock, Check, CheckCircle2, Download, HelpCircle, MessageSquare, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Badge, Button, Card, ErrorState, Notice, PageHeader, ProgressSteps, SectionTitle, Skeleton } from '@/ui/primitives';
import { ConfirmDialog } from '@/ui/overlays';
import { formatDate } from '@/lib/utils';
import { downloadDocument, useCreateConversation, useDeleteDocument, useDocument, useRetryDocument } from './api';

const STEPS = [
  { key: 'queued', label: 'Waiting to start' }, { key: 'parsing', label: 'Reading the file' },
  { key: 'indexing', label: 'Indexing for search' }, { key: 'reviewing', label: 'Reviewing the content' },
];

export const DocumentPage: React.FC = () => {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { data: d, isLoading, isError, error, refetch } = useDocument(id);
  const retry = useRetryDocument(id);
  const del = useDeleteDocument();
  const create = useCreateConversation();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const back = <Link to="/documents" className="inline-flex items-center gap-1 text-sm font-medium text-primary-ink hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden />Documents</Link>;
  // opens a chat scoped to this document's collection; the question (if any) is passed along to be asked first
  const startChat = (question?: string) => create.mutate({ collection: d?.category ?? null }, {
    onSuccess: (c) => navigate(`/documents/c/${c.id}`, { state: question ? { ask: question } : undefined }),
    onError: (e) => toast.error(toFriendlyError(e).message),
  });

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-64" /></div>;
  if (isError || !d) {
    const fe = toFriendlyError(error);
    return <div className="space-y-4">{back}<ErrorState title={fe.status === 404 ? 'Document not found' : 'Could not load this document'} message={fe.message} onRetry={fe.status === 404 ? undefined : () => refetch()} /></div>;
  }
  const fail = (e: unknown) => toast.error(toFriendlyError(e).message);
  const reviewing = d.status === 'ready' && d.review_state === 'pending';
  const byPage = new Map<string, typeof d.chunks>();
  d.chunks.forEach((c) => { const k = c.page ? `Page ${c.page}` : 'Text'; byPage.set(k, [...(byPage.get(k) ?? []), c]); });

  return (
    <>
      <PageHeader back={back} title={d.title} subtitle={[d.category ? `Collection: ${d.category}` : null, d.doc_type, d.language, d.file_type, d.page_count ? `${d.page_count} pages` : null, `Added ${formatDate(d.created_at)}`].filter(Boolean).join(' · ')}
        actions={<>
          {d.status === 'ready' && <Button size="sm" variant="secondary" icon={<Download className="h-4 w-4" aria-hidden />} onClick={() => downloadDocument(d.id, d.filename ?? 'document').catch(fail)}>Original</Button>}
          <Button size="sm" variant="ghost" aria-label="Delete document" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" aria-hidden /></Button>
        </>} />
      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} danger loading={del.isPending} title="Delete this document?" description="The file, its search index and any renewal reminder will be removed."
        confirmLabel="Delete" onConfirm={() => del.mutate(d.id, { onSuccess: () => { toast.success('Document deleted'); navigate('/documents'); }, onError: fail })} />

      {d.status === 'processing' && <Card className="mx-auto max-w-xl"><h2 className="text-lg font-semibold text-ink">Reading your document…</h2><div className="mt-4" aria-live="polite"><ProgressSteps steps={STEPS} current={d.stage ?? 'queued'} /></div></Card>}
      {d.status === 'failed' && <div className="mx-auto max-w-xl"><ErrorState title="We couldn't process this document" message={d.error_message ?? 'Something went wrong.'} onRetry={() => retry.mutate(undefined, { onError: fail })} retrying={retry.isPending} /></div>}

      {d.status === 'ready' && (
        <div className="space-y-6">
          {d.expiry_date && (
            <Notice tone="warn" title={`${d.expiry_label ?? 'Expires'}: ${formatDate(d.expiry_date)}`}>
              <CalendarClock className="mr-1 inline h-4 w-4" aria-hidden />{d.in_calendar ? <>Added to your <Link to="/compliance" className="font-semibold underline">compliance calendar</Link> so you can renew in time.</> : 'Check whether it needs renewing.'}
            </Notice>
          )}

          {d.suggested_questions.length > 0 && (
            <Card>
              <SectionTitle action={<Button size="sm" variant="secondary" icon={<MessageSquare className="h-4 w-4" aria-hidden />} loading={create.isPending} onClick={() => startChat()}>Ask about this</Button>}>Questions it can answer</SectionTitle>
              <ul className="flex flex-wrap gap-2">{d.suggested_questions.map((q) => <li key={q}><button onClick={() => startChat(q)} className="rounded-full border border-line px-3 py-1.5 text-sm text-ink-2 hover:border-line-strong hover:bg-surface-2 hover:text-ink">{q}</button></li>)}</ul>
            </Card>
          )}

          {reviewing && <Card><p className="text-sm text-ink-2">Reviewing the content to find the key points… you can already search and ask questions.</p></Card>}
          {d.review_state === 'failed' && <Notice tone="warn" title="The summary isn't available">{d.review_error} The document is still searchable. <button className="font-semibold underline" onClick={() => retry.mutate(undefined, { onError: fail })}>Try again</button></Notice>}

          {d.review_state === 'done' && (
            <div className="grid gap-5 md:grid-cols-2">
              <Card>
                <SectionTitle>In plain English</SectionTitle>
                <ul className="space-y-2.5">{d.summary_points.map((p) => <li key={p} className="flex gap-2.5 text-sm text-ink"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary-ink" aria-hidden />{p}</li>)}</ul>
              </Card>
              <Card>
                <SectionTitle>Key facts</SectionTitle>
                {d.key_facts.length ? <dl className="space-y-2 text-sm">{d.key_facts.map((f) => <div key={f.label}><dt className="text-ink-3">{f.label}</dt><dd className="font-medium text-ink">{f.value}</dd></div>)}</dl> : <p className="text-sm text-ink-2">No key facts found.</p>}
              </Card>
            </div>
          )}

          {d.review_state === 'done' && d.concerns.length > 0 && (
            <section aria-labelledby="concerns">
              <SectionTitle id="concerns">Worth checking</SectionTitle>
              <ul className="space-y-3">
                {d.concerns.map((c, i) => (
                  <li key={i} className="rounded-xl border border-line bg-surface p-4">
                    <p className="font-semibold text-ink">{c.title}</p>
                    <p className="text-sm text-ink-2">{c.why_it_matters}</p>
                    <figure className="mt-2 rounded-lg border-l-4 border-line-strong bg-surface-2 p-3">
                      <blockquote className="text-sm italic text-ink">“{c.quote}”</blockquote>
                      <figcaption className="mt-1 flex flex-wrap items-center gap-3 text-xs text-ink-3">
                        {c.page ? <span>Page {c.page}</span> : null}
                        {c.verified ? <span className="flex items-center gap-1 font-medium text-good-ink"><Check className="h-3.5 w-3.5" aria-hidden />Found in the document</span>
                          : <span className="flex items-center gap-1 font-medium text-warn-ink"><HelpCircle className="h-3.5 w-3.5" aria-hidden />Couldn't match this wording</span>}
                      </figcaption>
                    </figure>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {d.review_state === 'done' && d.missing_items.length > 0 && (
            <Card><SectionTitle>Usually included, but missing here</SectionTitle><ul className="flex flex-wrap gap-2">{d.missing_items.map((m) => <Badge key={m} tone="warn">{m}</Badge>)}</ul></Card>
          )}

          <details className="rounded-xl border border-line bg-surface p-4">
            <summary className="cursor-pointer text-sm font-medium text-ink">Text we read ({d.chunk_count} passages){d.ocr_used ? ' · from a scan, so please double-check figures' : ''}</summary>
            <div className="mt-3 max-h-[28rem] space-y-4 overflow-auto">
              {Array.from(byPage.entries()).map(([page, cs]) => (
                <div key={page}><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">{page}</p>
                  {cs.map((c) => <div key={c.chunk_index} className="mb-2">{c.section && <p className="text-xs font-medium text-ink-3">{c.section}</p>}<p className="whitespace-pre-wrap text-sm text-ink-2">{c.text}</p></div>)}</div>
              ))}
            </div>
          </details>
        </div>
      )}
    </>
  );
};
