import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarCheck, ClipboardPaste, FileText, Info, Scale, Sparkles, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { toFriendlyError } from '@/api/client';
import { Button, ErrorState, Field, Input, Textarea } from '@/ui/primitives';
import { cn } from '@/lib/utils';
import { useLoadSample } from '@/features/samples/api';
import { PhotoDropzone } from '@/features/shared/PhotoDropzone';
import { usePasteNotice, useUploadNotice, type NoticeListItem } from './api';
import { todayIso } from './lib';

const GET: [React.ElementType, string, string][] = [
  [CalendarCheck, 'The real deadline', 'Counted from the day you received it and added to your calendar, so it cannot slip.'],
  [Scale, 'What it means', 'Who wants what, the law behind it, and what happens if you ignore it, in plain English.'],
  [FileText, 'A reply to send', 'A draft in your name with blanks only you can fill, ready for your lawyer to review.'],
];

type Mode = 'upload' | 'paste';

const Choice: React.FC<{ active: boolean; onClick: () => void; icon: React.ReactNode; title: string; hint: string }> = ({ active, onClick, icon, title, hint }) => (
  <button type="button" role="radio" aria-checked={active} onClick={onClick}
    className={cn('flex items-start gap-3 rounded-2xl p-5 text-left transition-[background-color,box-shadow]', active ? 'bg-surface-2 ring-2 ring-primary' : 'bg-surface-2 ring-1 ring-transparent hover:shadow-card hover:ring-line-strong')}>
    <span className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl', active ? 'bg-primary text-primary-on btn-raised' : 'bg-surface text-ink-2 shadow-card')} aria-hidden>{icon}</span>
    <span><span className="block font-semibold text-ink">{title}</span><span className="block text-sm text-ink-2">{hint}</span></span>
  </button>
);

export const Intake: React.FC = () => {
  const navigate = useNavigate();
  const upload = useUploadNotice();
  const paste = usePasteNotice();
  const sample = useLoadSample();
  const [mode, setMode] = useState<Mode>('upload');
  const [files, setFiles] = useState<File[]>([]);
  const [text, setText] = useState('');
  const [received, setReceived] = useState(todayIso());
  const pending = upload.isPending || paste.isPending;
  const err = upload.isError ? toFriendlyError(upload.error).message : paste.isError ? toFriendlyError(paste.error).message : null;
  const ready = (mode === 'upload' ? files.length > 0 : text.trim().length >= 40) && !!received;
  const done = (n: NoticeListItem) => { toast.success('Notice added. Reading it now.'); navigate(`/notices/${n.id}`); };
  const go = () => (mode === 'upload' && files.length ? upload.mutate({ files, receivedDate: received }, { onSuccess: done }) : paste.mutate({ text, received_date: received }, { onSuccess: done }));
  const loadSample = () => sample.mutate('notice', { onSuccess: (r) => { toast.success('Sample notice added. Reading it now.'); navigate(r.path); }, onError: (e) => toast.error(toFriendlyError(e).message) });

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-10 px-6 pb-16 pt-20 sm:px-10 lg:grid-cols-[1.15fr_1fr] lg:gap-16 lg:pt-24 xl:px-14">
      <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">Response desk</p>
      <h1 className="mt-3 font-display text-[2.4rem] font-normal leading-[1.08] tracking-[-0.01em] text-ink sm:text-[3.2rem]">A legal notice arrived. Let's work out what to do.</h1>
      <p className="mt-4 max-w-xl text-[15px] text-ink-2">Add the notice. In under a minute you will know what it says and how long you have, with a reply ready for your lawyer.</p>

      <div role="radiogroup" aria-label="How do you want to add it?" className="mt-10 grid gap-3 sm:grid-cols-2">
        <Choice active={mode === 'upload'} onClick={() => setMode('upload')} icon={<Upload className="h-5 w-5" />} title="Upload the notice" hint="PDF, photos of each page, Word or text file" />
        <Choice active={mode === 'paste'} onClick={() => setMode('paste')} icon={<ClipboardPaste className="h-5 w-5" />} title="Paste the text" hint="From an email or WhatsApp message" />
      </div>

      <div className="mt-4">
        {mode === 'upload'
          ? <PhotoDropzone accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp" files={files} onFiles={setFiles} disabled={pending} hint="PDF, Word or text, or several photos of the pages · up to 10 MB each" />
          : <Field label="Notice text">{({ id }) => <Textarea id={id} rows={9} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the full text of the notice here" disabled={pending} className="font-serif text-[15px] leading-7" />}</Field>}
      </div>

      <div className="mt-5 flex flex-wrap items-end gap-4">
        <div className="w-full sm:w-60">
          <Field label="Day you received it" hint="Reply windows usually count from this day.">{({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} type="date" max={todayIso()} value={received} onChange={(e) => setReceived(e.target.value)} />}</Field>
        </div>
        <Button size="lg" className="h-12" icon={<Upload className="h-4 w-4" aria-hidden />} loading={pending} disabled={!ready} onClick={go}>Read this notice</Button>
        <Button size="lg" variant="ghost" className="h-12" loading={sample.isPending} disabled={pending} icon={<Sparkles className="h-4 w-4" aria-hidden />} onClick={loadSample}>Try a sample notice</Button>
      </div>
      {err && <ErrorState className="mt-4" title="Couldn't add this notice" message={err} />}
      <p className="mt-8 flex items-start gap-2 text-xs text-ink-3"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />Decision support, not legal advice. Have a lawyer read your reply before you send it.</p>
      </div>

      <div className="lg:pt-24">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">What you get</p>
        <ul className="mt-4 space-y-3">
          {GET.map(([Icon, title, body]) => (
            <li key={title} className="flex gap-4 rounded-2xl bg-surface-2 p-4 transition-shadow hover:shadow-card">
              <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface text-ink-2 shadow-card" aria-hidden><Icon className="h-4 w-4" /></span>
              <span><span className="block text-[15px] font-semibold text-ink">{title}</span><span className="mt-0.5 block text-sm leading-relaxed text-ink-2">{body}</span></span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
