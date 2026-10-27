import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import * as Popover from '@radix-ui/react-popover';
import { ChevronRight, CircleUserRound, LogOut } from 'lucide-react';
import { useSession, type DemoPersona } from '@/lib/auth/session';
import { cn } from '@/lib/utils';
import { Hint } from '@/ui/overlays';

const PERSONAS: { key: DemoPersona; label: string }[] = [
  { key: 'owner', label: 'Business owner' },
  { key: 'ca', label: 'Chartered Accountant' },
  { key: 'reviewer', label: 'Legal reviewer' },
];

const rowCls = 'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-ink transition-colors hover:bg-surface-2';

/** Account card dropped from the top strip: avatar, name, email, then the account actions. */
export const UserMenu: React.FC<{ compact?: boolean }> = ({ compact }) => {
  const { user, org, logout, startDemo } = useSession();
  const location = useLocation();
  if (!user) return null;
  const initials = user.full_name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();
  const trigger = (
    <button className={cn('flex items-center gap-2 rounded-lg text-ink-2 transition-colors hover:bg-surface-2/80 hover:text-ink', compact ? 'h-8 w-8 justify-center' : 'px-2 py-1.5')} aria-label="Account">
      <CircleUserRound className="h-[19px] w-[19px]" strokeWidth={1.8} aria-hidden />
      {!compact && <span className="text-sm font-medium">{user.full_name}</span>}
    </button>
  );
  return (
    <Popover.Root>
      {compact ? <Hint text="Account"><Popover.Trigger asChild>{trigger}</Popover.Trigger></Hint> : <Popover.Trigger asChild>{trigger}</Popover.Trigger>}
      <Popover.Portal>
        <Popover.Content align="start" sideOffset={6} className="z-50 w-[21rem] max-w-[calc(100vw-1rem)] rounded-2xl border border-line bg-surface p-2 shadow-float animate-scale-in [--origin:top_left]">
          <div className="flex items-center gap-3 px-3 py-2.5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-peach text-sm font-semibold text-peach-ink" aria-hidden>{initials}</span>
            <span className="min-w-0">
              <span className="block truncate text-[15px] font-semibold text-ink">{user.full_name}</span>
              <span className="block truncate text-xs text-ink-2">{user.is_demo ? `Sample company · ${org?.legal_name ?? ''}` : user.email}</span>
            </span>
          </div>
          <div className="my-1 h-px bg-line" />
          {user.is_demo && (
            <div className="px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">View as</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {PERSONAS.map((p) => (
                  <button key={p.key} className="rounded-full border border-line px-2.5 py-1 text-xs font-medium text-ink hover:bg-surface-2"
                    onClick={() => { void startDemo(p.key).then(() => window.location.reload()); }}>{p.label}</button>
                ))}
              </div>
            </div>
          )}
          <Popover.Close asChild>
            <Link to="/settings" state={location.pathname === '/settings' ? undefined : { background: location }} className={rowCls}><span className="flex-1">Manage account</span><ChevronRight className="h-4 w-4 text-ink-3" aria-hidden /></Link>
          </Popover.Close>
          <button className={rowCls} onClick={logout}><LogOut className="h-4 w-4 text-ink-3" aria-hidden />Sign out</button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
};
