import React, { useEffect, useId, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, FileUp, Images, X } from 'lucide-react';
import { cn, fileSize } from '@/lib/utils';

const isImage = (f: File) => f.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(f.name);

/** Combine what was already chosen with new picks: photos stack up in order, any other document stands alone. */
export function mergeFiles(current: File[], picked: File[]): File[] {
  if (!picked.length) return current;
  const first = picked[0];
  if (!isImage(first)) return [first];
  const photos = picked.filter(isImage);
  return [...current.filter(isImage), ...photos];
}

/** Upload box that takes one document or several page photos (kept in order, with a thumbnail strip). */
export const PhotoDropzone: React.FC<{
  accept: string;
  files: File[];
  onFiles: (f: File[]) => void;
  disabled?: boolean;
  hint?: string;
  maxPhotos?: number;
}> = ({ accept, files, onFiles, disabled, hint, maxPhotos = 12 }) => {
  const id = useId();
  const [over, setOver] = useState(false);
  const photos = files.length > 0 && files.every(isImage);
  const urls = useMemo(() => (photos ? files.map((f) => URL.createObjectURL(f)) : []), [files, photos]);
  useEffect(() => () => urls.forEach((u) => URL.revokeObjectURL(u)), [urls]);

  const take = (list: FileList | null | undefined) => {
    if (!list || list.length === 0) return;
    onFiles(mergeFiles(files, Array.from(list)).slice(0, maxPhotos));
  };
  const move = (i: number, by: number) => {
    const j = i + by;
    if (j < 0 || j >= files.length) return;
    const next = [...files];
    [next[i], next[j]] = [next[j], next[i]];
    onFiles(next);
  };

  return (
    <div>
      <label
        htmlFor={id}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); if (!disabled) take(e.dataTransfer.files); }}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors',
          'focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--ring)]',
          over ? 'border-primary bg-primary-soft' : 'border-line-strong bg-surface hover:bg-surface-2',
          disabled && 'cursor-not-allowed opacity-60',
        )}
      >
        {photos ? <Images className="mb-2 h-8 w-8 text-primary-ink" aria-hidden /> : <FileUp className="mb-2 h-8 w-8 text-primary-ink" aria-hidden />}
        {files.length === 0 ? (
          <>
            <span className="font-semibold text-ink">Drop a file here, or click to choose</span>
            <span className="text-sm text-ink-2">{hint}</span>
          </>
        ) : photos ? (
          <>
            <span className="font-semibold text-ink">{files.length === 1 ? '1 photo' : `${files.length} photos, in page order`}</span>
            <span className="text-sm text-ink-2">Click to add more pages</span>
          </>
        ) : (
          <>
            <span className="font-semibold text-ink">{files[0].name}</span>
            <span className="text-sm text-ink-2">{fileSize(files[0].size)} · click to choose a different file</span>
          </>
        )}
        <input id={id} type="file" multiple accept={accept} disabled={disabled} className="sr-only"
          onChange={(e) => { take(e.target.files); e.target.value = ''; }} />
      </label>

      {photos && (
        <ol className="mt-3 flex gap-2.5 overflow-x-auto pb-1" aria-label="Pages, in order">
          {files.map((f, i) => (
            <li key={`${f.name}-${f.size}-${i}`} className="relative shrink-0">
              <img src={urls[i]} alt={`Page ${i + 1}`} className="h-24 w-[4.5rem] rounded-lg border border-line-strong object-cover shadow-card" />
              <span className="absolute left-1 top-1 rounded-full bg-primary px-1.5 text-[10px] font-semibold tabular-nums text-primary-on">{i + 1}</span>
              <button type="button" disabled={disabled} onClick={() => onFiles(files.filter((_, k) => k !== i))} aria-label={`Remove page ${i + 1}`}
                className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-surface text-ink-2 shadow-card hover:text-ink"><X className="h-3 w-3" aria-hidden /></button>
              {files.length > 1 && (
                <div className="mt-1 flex justify-between">
                  <button type="button" disabled={disabled || i === 0} onClick={() => move(i, -1)} aria-label={`Move page ${i + 1} earlier`} className="rounded p-0.5 text-ink-3 hover:text-ink disabled:opacity-30"><ArrowLeft className="h-3.5 w-3.5" aria-hidden /></button>
                  <button type="button" disabled={disabled || i === files.length - 1} onClick={() => move(i, 1)} aria-label={`Move page ${i + 1} later`} className="rounded p-0.5 text-ink-3 hover:text-ink disabled:opacity-30"><ArrowRight className="h-3.5 w-3.5" aria-hidden /></button>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
};
