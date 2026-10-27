import React, { useEffect, useState } from 'react';
import { X, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Hint } from '@/ui/overlays';

function readOpen(key: string, fallback: boolean): boolean {
  try { const v = localStorage.getItem(`legalos_panel_${key}`); return v === null ? fallback : v === 'open'; } catch { return fallback; }
}

/**
 * A collapsible panel on the right edge of a workspace, opened by a round floating button.
 * Keeps the centre of the screen for the thing that matters (the document, the search, the chat) and tucks
 * history / lists / explanations away until they are wanted. The host must be `relative h-full overflow-hidden`.
 */
export const SidePanel: React.FC<{
  storageKey: string;
  title: string;
  icon: LucideIcon;
  count?: number;
  defaultOpen?: boolean;
  width?: string;
  /** Extra floating buttons rendered next to the toggle (e.g. "New"). */
  actions?: React.ReactNode;
  children: React.ReactNode;
  /** Called when the open state changes, so the host can add right padding when the panel pushes content. */
  onOpenChange?: (open: boolean) => void;
}> = ({ storageKey, title, icon: Icon, count, defaultOpen = false, width = 'w-[340px]', actions, children, onOpenChange }) => {
  const [open, setOpen] = useState(() => readOpen(storageKey, defaultOpen));
  useEffect(() => {
    try { localStorage.setItem(`legalos_panel_${storageKey}`, open ? 'open' : 'closed'); } catch { /* ignore */ }
    onOpenChange?.(open);
  }, [open, storageKey, onOpenChange]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onClose = (e: Event) => { if ((e as CustomEvent<string>).detail === storageKey || !(e as CustomEvent).detail) setOpen(false); };
    window.addEventListener('legalos:panel-close', onClose);
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('legalos:panel-close', onClose); };
  }, [open, storageKey]);

  return (
    <>
      {/* Floating controls, top-right of the sheet */}
      <div className={cn('absolute right-4 top-4 z-30 flex items-center gap-2 transition-transform duration-200', open && 'max-md:-translate-x-0')}>
        {actions}
        <Hint text={open ? `Hide ${title.toLowerCase()}` : title}>
          <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls={`panel-${storageKey}`}
            className={cn('btn-quiet relative flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface text-ink-2 transition-colors hover:text-ink', open && 'bg-surface-2 text-ink')}>
            {open ? <X className="h-[18px] w-[18px]" aria-hidden /> : <Icon className="h-[18px] w-[18px]" strokeWidth={1.9} aria-hidden />}
            {!open && count !== undefined && count > 0 && (
              <span className="absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-ink px-1 text-[10px] font-semibold text-app" aria-hidden>{count}</span>
            )}
          </button>
        </Hint>
      </div>

      {/* Scrim on small screens */}
      <div className={cn('absolute inset-0 z-10 bg-black/20 transition-opacity md:hidden', open ? 'opacity-100' : 'pointer-events-none opacity-0')} onClick={() => setOpen(false)} aria-hidden />

      <aside id={`panel-${storageKey}`} aria-label={title} aria-hidden={!open}
        className={cn('absolute inset-y-0 right-0 z-20 flex max-w-[calc(100%-1rem)] flex-col border-l border-line bg-surface shadow-float transition-transform duration-200 ease-out',
          width, open ? 'translate-x-0' : 'translate-x-full')}>
        <div className="flex h-[84px] shrink-0 items-end px-5 pb-2.5">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">{title}{count !== undefined && <span className="ml-2 text-ink-3">{count}</span>}</h2>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">{children}</div>
      </aside>
    </>
  );
};

/** Close a SidePanel from anywhere (e.g. after picking a row on a phone). Omit the key to close all. */
export function closeSidePanel(storageKey?: string): void {
  window.dispatchEvent(new CustomEvent('legalos:panel-close', { detail: storageKey }));
}

/** A small uppercase label for a group inside a panel. */
export const PanelLabel: React.FC<{ children: React.ReactNode; action?: React.ReactNode }> = ({ children, action }) => (
  <div className="mb-1.5 mt-4 flex items-center justify-between px-2 first:mt-0">
    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">{children}</p>
    {action}
  </div>
);
