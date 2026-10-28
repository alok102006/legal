import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Building2, CircleHelp, Menu as MenuIcon, Moon, PanelLeft, Search, Settings, Sun, X } from 'lucide-react';
import { useSession } from '@/lib/auth/session';
import { useTheme } from '@/lib/theme';
import { useHealth } from '@/api/health';
import { cn } from '@/lib/utils';
import { Hint, TooltipProviderRoot } from '@/ui/overlays';
import { Notice } from '@/ui/primitives';
import { Logo, LogoMark } from '@/ui/logo';
import { ErrorBoundary } from '@/ui/ErrorBoundary';
import { UserMenu } from './UserMenu';
import { NAV, pageTitle } from './nav';
import { CommandPalette } from './CommandPalette';
import { NotificationsBell } from './Notifications';

/* ------------------------------------------------------------------ pieces */

const StripButton: React.FC<React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string }> = ({ label, className, children, ...rest }) => (
  <Hint text={label}>
    <button className={cn('flex h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition-colors hover:bg-surface-2/80 hover:text-ink', className)} aria-label={label} {...rest}>
      {children}
    </button>
  </Hint>
);

const ThemeButton: React.FC = () => {
  const { theme, setTheme } = useTheme();
  const dark = theme === 'dark' || (theme === 'system' && typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  return (
    <StripButton label={dark ? 'Light mode' : 'Dark mode'} onClick={() => setTheme(dark ? 'light' : 'dark')}>
      {dark ? <Sun className="h-[17px] w-[17px]" aria-hidden /> : <Moon className="h-[17px] w-[17px]" aria-hidden />}
    </StripButton>
  );
};

/** One sidebar row. Labels fade while the rail narrows, like the reference. */
const Row: React.FC<{ to: string; icon: React.ElementType; label: string; end?: boolean; collapsed: boolean; badge?: React.ReactNode; onNavigate?: () => void; state?: unknown }> =
  ({ to, icon: Icon, label, end, collapsed, badge, onNavigate, state }) => {
    const link = (
      <NavLink to={to} end={end} state={state} onClick={onNavigate} aria-label={collapsed ? label : undefined}
        className={({ isActive }) => cn('relative flex h-10 items-center gap-3 rounded-xl px-2.5 text-[15px] font-medium transition-colors',
          isActive ? 'bg-surface-2 text-ink' : 'text-ink hover:bg-surface-2/70')}>
        <Icon className="h-[19px] w-[19px] shrink-0" strokeWidth={1.9} aria-hidden />
        <span className={cn('fade-labels min-w-0 flex-1 truncate', collapsed ? 'pointer-events-none -translate-x-1 opacity-0' : 'opacity-100')}>{label}</span>
        {badge && <span className={cn('absolute', collapsed ? 'right-0.5 top-1' : 'right-2.5 top-1/2 -translate-y-1/2')}>{badge}</span>}
      </NavLink>
    );
    return collapsed ? <Hint text={label}>{link}</Hint> : link;
  };

const SystemDot: React.FC = () => {
  const { data, isLoading, isError } = useHealth();
  const down = isError || data?.status === 'unhealthy';
  const llmDown = !down && !!data && !data.checks.llm.ok;
  const label = isLoading ? 'Checking system…' : down ? 'Server unreachable' : llmDown ? 'AI service unavailable' : 'All systems working';
  const bad = down || llmDown;
  return (
    <Hint text={label}>
      <span className="flex h-5 w-5 items-center justify-center" role="status" aria-label={label}>
        {bad ? <AlertTriangle className="h-3.5 w-3.5 text-critical-ink" aria-hidden /> : <span className={cn('h-2 w-2 rounded-full', isLoading ? 'bg-ink-3' : 'bg-good')} aria-hidden />}
      </span>
    </Hint>
  );
};

const Sidebar: React.FC<{ collapsed: boolean; onNavigate?: () => void }> = ({ collapsed, onNavigate }) => {
  const { org } = useSession();
  const location = useLocation();
  const settingsState = location.pathname === '/settings' ? undefined : { background: location };
  const { data: health } = useHealth();
  const attention = health && !health.checks.llm.ok;
  const main = NAV.filter((n) => n.to !== '/settings');
  return (
    <div className="flex h-full flex-col">
      <NavLink to="/" aria-label="Home" className="flex h-10 items-center px-2.5">
        {collapsed ? <LogoMark size={26} /> : <Logo size={26} textClassName="text-[20px]" />}
      </NavLink>
      <nav className="mt-4 flex-1 space-y-0.5 overflow-y-auto px-0" aria-label="Main">
        {main.map((n) => <Row key={n.to} to={n.to} icon={n.icon} label={n.label} end={n.end} collapsed={collapsed} onNavigate={onNavigate} />)}
      </nav>
      {!collapsed && org && (
        <NavLink to="/settings" state={settingsState} onClick={onNavigate} className="mb-3 flex items-center gap-2.5 rounded-xl border border-line bg-surface p-2.5 shadow-card transition-colors hover:border-line-strong">
          <Building2 className="h-4 w-4 shrink-0 text-ink-2" aria-hidden />
          <span className="min-w-0"><span className="block truncate text-[13px] font-medium text-ink">{org.legal_name}</span><span className="block text-[11px] text-ink-3">{org.onboarding_completed ? 'Profile complete' : 'Finish company setup'}</span></span>
        </NavLink>
      )}
      <div className="space-y-0.5 pb-1">
        <Row to="/settings" state={settingsState} icon={Settings} label="Settings" collapsed={collapsed} onNavigate={onNavigate}
          badge={attention ? <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-critical px-1 text-[10px] font-bold text-white">1</span> : undefined} />
        <div className={cn('flex h-10 items-center gap-3 rounded-xl px-2.5 text-[15px] font-medium text-ink', collapsed && 'justify-center px-0')}>
          {collapsed ? <SystemDot /> : (
            <>
              <CircleHelp className="h-[19px] w-[19px] shrink-0 text-ink-2" strokeWidth={1.9} aria-hidden />
              <span className="fade-labels min-w-0 flex-1 truncate text-ink-2">System status</span>
              <SystemDot />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const HealthBanner: React.FC = () => {
  const { data } = useHealth();
  if (!data || data.checks.llm.ok) return null;
  return <div className="mb-6"><Notice tone="warn" title="AI analysis is currently unavailable">{data.checks.llm.message ?? 'The AI service is not responding.'} You can still browse your data; new analyses will fail until this is fixed.</Notice></div>;
};

function readCollapsed(): boolean { try { return localStorage.getItem('legalos_sidebar') === 'collapsed'; } catch { return false; } }

/* ------------------------------------------------------------------ shell */

export const AppShell: React.FC = () => {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [drawer, setDrawer] = useState(false);
  const [palette, setPalette] = useState(false);

  useEffect(() => { try { localStorage.setItem('legalos_sidebar', collapsed ? 'collapsed' : 'open'); } catch { /* ignore */ } }, [collapsed]);
  useEffect(() => { setDrawer(false); }, [pathname]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette((p) => !p); }
      if ((e.ctrlKey || e.metaKey) && e.key === '\\') { e.preventDefault(); setCollapsed((c) => !c); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const title = pageTitle(pathname);
  useEffect(() => { document.title = `${title} · LegalOS`; }, [title]);

  // Workspaces own the whole sheet (list + detail panes); Home and Settings scroll inside it.
  const fullBleed = pathname === '/documents' || pathname.startsWith('/documents/c/')
    || ['/contracts', '/vendors', '/notices', '/compliance'].some((p) => pathname === p || pathname.startsWith(p + '/'));

  return (
    <TooltipProviderRoot>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-on">Skip to main content</a>

      <div className="flex h-screen flex-col bg-app">
        {/* Top strip: icons only, like a native title bar */}
        <header className="flex h-11 shrink-0 items-center justify-between px-2.5">
          <div className="flex items-center gap-0.5">
            <StripButton label="Menu" className="md:hidden" onClick={() => setDrawer(true)}><MenuIcon className="h-[18px] w-[18px]" aria-hidden /></StripButton>
            <StripButton label={collapsed ? 'Show sidebar (Ctrl+\\)' : 'Hide sidebar (Ctrl+\\)'} className="hidden md:flex" onClick={() => setCollapsed((c) => !c)} aria-pressed={!collapsed}>
              <PanelLeft className="h-[18px] w-[18px]" aria-hidden />
            </StripButton>
            <UserMenu compact />
          </div>
          <div className="flex items-center gap-0.5">
            <StripButton label="Search (Ctrl+K)" onClick={() => setPalette(true)}><Search className="h-[17px] w-[17px]" aria-hidden /></StripButton>
            <ThemeButton />
            <NotificationsBell />
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          {/* Desktop sidebar: sits on the frame, no border */}
          <aside className={cn('hidden shrink-0 flex-col px-2.5 pb-2 transition-[width] duration-200 ease-out md:flex', collapsed ? 'w-[64px]' : 'w-[240px]')} aria-label="Sidebar">
            <Sidebar collapsed={collapsed} />
          </aside>

          {/* The sheet */}
          <main id="main" tabIndex={-1} className={cn('sheet relative mb-2 mr-2 min-w-0 flex-1 overflow-hidden rounded-2xl bg-surface max-md:ml-2', fullBleed ? '' : 'overflow-y-auto')}>
            {fullBleed ? <div className="h-full"><ErrorBoundary resetKey={pathname}><Outlet /></ErrorBoundary></div> : (
              <div className="mx-auto w-full max-w-7xl px-5 pb-16 pt-8 sm:px-10 lg:px-12">
                <HealthBanner />
                <div key={pathname} className="animate-in"><ErrorBoundary resetKey={pathname}><Outlet /></ErrorBoundary></div>
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Mobile drawer */}
      <Dialog.Root open={drawer} onOpenChange={setDrawer}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 md:hidden" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-app px-3 pb-3 pt-2 shadow-2xl md:hidden" aria-label="Menu">
            <Dialog.Title className="sr-only">Menu</Dialog.Title>
            <div className="flex justify-end"><Dialog.Close asChild><button className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-3 hover:bg-surface-2" aria-label="Close menu"><X className="h-5 w-5" aria-hidden /></button></Dialog.Close></div>
            <div className="min-h-0 flex-1"><Sidebar collapsed={false} onNavigate={() => setDrawer(false)} /></div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <CommandPalette open={palette} onOpenChange={setPalette} />
    </TooltipProviderRoot>
  );
};
