import React from 'react';
import { Link } from 'react-router-dom';
import * as Popover from '@radix-ui/react-popover';
import { Bell, BellRing, BookOpen, CalendarCheck, CheckCircle2, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAttention, type AttentionItem } from './useAttention';

const ICON: Record<AttentionItem['kind'], React.ElementType> = { notice: BellRing, contract: FileText, compliance: CalendarCheck, document: BookOpen };

export const NotificationsBell: React.FC = () => {
  const { items } = useAttention();
  const urgent = items.filter((i) => i.level !== 'medium').length;
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button className="relative flex h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition-colors hover:bg-surface-2/80 hover:text-ink" aria-label={`Notifications${items.length ? `, ${items.length} items` : ''}`}>
          <Bell className="h-[17px] w-[17px]" aria-hidden />
          {items.length > 0 && (
            <span className={cn('absolute right-0.5 top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-bold text-white', urgent ? 'bg-critical' : 'bg-ink-3')} aria-hidden>{items.length}</span>
          )}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} className="z-50 w-[26rem] max-w-[calc(100vw-1rem)] rounded-3xl bg-surface p-6 shadow-float animate-scale-in [--origin:top_right]">
          <p className="mb-4 text-lg font-semibold text-ink">Notifications</p>
          {items.length === 0 ? (
            <p className="flex items-center gap-3 rounded-2xl bg-surface-2 px-4 py-4 text-sm text-ink-2"><CheckCircle2 className="h-5 w-5 text-good-ink" aria-hidden />You're all caught up. Nothing needs you right now.</p>
          ) : (
            <ul className="-mx-2 max-h-[60vh] space-y-1 overflow-y-auto">
              {items.slice(0, 8).map((i) => {
                const Icon = ICON[i.kind];
                return (
                  <li key={i.kind + i.id}>
                    <Popover.Close asChild>
                      <Link to={i.link} className="flex gap-4 rounded-2xl px-2 py-2.5 transition-colors hover:bg-surface-2">
                        <span className={cn('flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-xl', i.level === 'critical' ? 'bg-peach text-peach-ink' : 'bg-lavender text-lavender-ink')} aria-hidden><Icon className="h-5 w-5" /></span>
                        <span className="min-w-0 py-0.5"><span className="block text-[15px] font-medium leading-snug text-ink">{i.title}</span><span className="mt-0.5 block text-sm leading-snug text-ink-2">{i.detail}</span></span>
                      </Link>
                    </Popover.Close>
                  </li>
                );
              })}
            </ul>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
};
