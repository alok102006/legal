/** The response desk: the selected notice (or the intake stage) in the centre; your notices, sorted by time left, in the right-hand side panel. */
import React, { useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Clock, History, Loader2, Plus } from 'lucide-react';
import { toFriendlyError } from '@/api/client';
import { EmptyState, ErrorState, SkeletonRows } from '@/ui/primitives';
import { closeSidePanel, PanelLabel, SidePanel } from '@/ui/sidepanel';
import { cn, formatINR } from '@/lib/utils';
import { useNotices, type NoticeListItem } from './api';
import { countdown, sortNotices, TONE_PILL } from './lib';
import { Intake } from './Intake';
import { NoticeView } from './NoticeView';

export const Pill: React.FC<{ n: Pick<NoticeListItem, 'status' | 'days_left' | 'response_deadline'>; className?: string }> = ({ n, className }) => {
  const c = countdown(n);
  return (
    <span className={cn('inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums', TONE_PILL[c.tone], className)}>
      {n.status === 'processing' ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> : <Clock className="h-3 w-3" aria-hidden />}
      {c.pill}
    </span>
  );
};

/** On a phone the panel covers the page, so close it once a choice is made. */
const closePanelOnPhone = () => {
  try { if (window.matchMedia('(max-width: 767px)').matches) closeSidePanel('notices-list'); } catch { /* ignore */ }
};

const Row: React.FC<{ n: NoticeListItem; active: boolean }> = ({ n, active }) => {
  const sender = n.issuer_name || n.title || n.source_name || 'Notice';
  const sub = [n.status === 'analyzed' || n.status === 'closed' ? n.title : n.source_name, n.amount_claimed ? formatINR(n.amount_claimed) : null].filter(Boolean).join(' · ');
  return (
    <li>
      <Link to={`/notices/${n.id}`} aria-current={active ? 'page' : undefined} onClick={closePanelOnPhone}
        className={cn('block rounded-xl px-2.5 py-2 transition-colors hover:bg-surface-2', active && 'bg-surface-2', n.status === 'closed' && !active && 'opacity-75')}>
        <span className="flex items-center justify-between gap-2">
          <span className="min-w-0 truncate text-xs text-ink-3">{n.type_label ?? (n.status === 'processing' ? 'Reading notice' : 'Notice')}</span>
          <Pill n={n} />
        </span>
        <span className="mt-1 block truncate text-[13.5px] font-medium text-ink">{sender}</span>
        {sub && <span className="block truncate text-xs text-ink-3">{sub}</span>}
      </Link>
    </li>
  );
};

const NoticeList: React.FC<{ id?: string; list: NoticeListItem[]; isLoading: boolean; isError: boolean; error: unknown; loaded: boolean; refetch: () => void }> = ({ id, list, isLoading, isError, error, loaded, refetch }) => {
  const open = list.filter((n) => n.status !== 'closed');
  const replied = list.filter((n) => n.status === 'closed');
  return (
    <div>
      {isLoading && <SkeletonRows rows={4} className="px-2" />}
      {isError && <ErrorState title="Couldn't load notices" message={toFriendlyError(error).message} onRetry={() => refetch()} />}
      {loaded && list.length === 0 && (
        <EmptyState icon={<Clock className="h-5 w-5" />} title="No notices yet" className="py-10"
          description="Add the first one and it will show here with its countdown."
          action={<Link to="/notices?new=1" onClick={closePanelOnPhone} className="btn-raised inline-flex h-9 items-center rounded-xl bg-primary px-3.5 text-[13px] font-medium text-primary-on hover:bg-primary-hover">Add a notice</Link>} />
      )}
      {open.length > 0 && (
        <>
          <PanelLabel>Closest deadline first</PanelLabel>
          <ul className="space-y-0.5">{open.map((n) => <Row key={n.id} n={n} active={n.id === id} />)}</ul>
        </>
      )}
      {replied.length > 0 && (
        <>
          <PanelLabel>Replied</PanelLabel>
          <ul className="space-y-0.5">{replied.map((n) => <Row key={n.id} n={n} active={n.id === id} />)}</ul>
        </>
      )}
    </div>
  );
};

export const NoticesWorkspace: React.FC<{ id?: string }> = ({ id }) => {
  const { data, isLoading, isError, error, refetch } = useNotices();
  const list = useMemo(() => sortNotices(data ?? []), [data]);
  const openCount = list.filter((n) => n.status !== 'closed').length;
  const { search } = useLocation();   // `?new=1` after a notice id remounts the intake so a fresh form appears
  // `/notices` and `/notices?new=1` both show the intake stage; a notice id shows the response desk
  return (
    <div className="relative h-full overflow-hidden">
      <SidePanel storageKey="notices-list" title="Your notices" icon={History} count={openCount}
        actions={
          <Link to="/notices?new=1" onClick={closePanelOnPhone} aria-label="New notice"
            className="btn-raised inline-flex h-10 items-center justify-center gap-1.5 rounded-full bg-primary px-3 text-sm font-medium text-primary-on transition-[background-color,box-shadow,transform] hover:bg-primary-hover sm:px-4">
            <Plus className="h-4 w-4" aria-hidden /><span className="hidden sm:inline">New notice</span>
          </Link>
        }>
        <NoticeList id={id} list={list} isLoading={isLoading} isError={isError} error={error} loaded={!!data} refetch={() => { void refetch(); }} />
      </SidePanel>
      <section aria-label={id ? 'Notice' : 'Add a notice'} className="h-full overflow-y-auto">
        {id ? <NoticeView key={id} id={id} /> : <Intake key={search} />}
      </section>
    </div>
  );
};
