import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { 
  FileText, 
  Users, 
  Bell, 
  Activity, 
  BookOpen, 
  Menu, 
  X,
  Scale,
  Search,
  ShieldCheck,
  Zap,
  Building2,
  ChevronDown
} from 'lucide-react';
import { RoleSwitcher } from '@/lib/auth/AuthContext';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const navigation = [
    { name: 'Executive Dashboard & Contracts', shortName: 'Contracts', href: '/', icon: FileText, active: true },
    { name: 'Vendor Intelligence & GSTIN', shortName: 'Vendors', href: '/vendors', icon: Users, active: true },
    { name: 'Statutory Compliance Center', shortName: 'Compliance', href: '/compliance', icon: Activity, active: true },
    { name: 'Legal Notice Center', shortName: 'Notices', href: '/notices', icon: Bell, active: true },
    { name: 'Knowledge & Precedents Hub', shortName: 'Knowledge', href: '/knowledge', icon: BookOpen, active: true },
  ];

  // Generate dynamic breadcrumb items
  const pathSegments = location.pathname.split('/').filter(Boolean);
  const getBreadcrumbs = () => {
    const crumbs = [{ label: 'LegalOS Enterprise', href: '/' }];
    if (pathSegments.length === 0) {
      crumbs.push({ label: 'Contract Intelligence Studio', href: '/' });
      return crumbs;
    }

    let accPath = '';
    for (const seg of pathSegments) {
      accPath += `/${seg}`;
      const matched = navigation.find(n => n.href === accPath);
      if (matched) {
        crumbs.push({ label: matched.name, href: matched.href });
      } else if (seg === 'contracts') {
        crumbs.push({ label: 'Contracts', href: '/' });
      } else if (seg.length > 20) {
        crumbs.push({ label: `Document (${seg.slice(0, 8)}...)`, href: accPath });
      } else {
        crumbs.push({ label: seg.charAt(0).toUpperCase() + seg.slice(1).replace(/-/g, ' '), href: accPath });
      }
    }
    return crumbs;
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[#090D16] text-[#DDE2F7]">
      {/* Mobile top bar header */}
      <header className="md:hidden flex items-center justify-between bg-[#0D1322] border-b border-white/10 px-4 py-3 shadow-md">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-600/20 border border-blue-500/30">
            <Scale className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <span className="font-bold text-base tracking-tight text-white">LegalOS</span>
            <span className="block text-[9px] font-mono text-blue-400 font-medium tracking-wider">ENTERPRISE</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <RoleSwitcher />
          <button 
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 text-slate-300 hover:bg-white/10 rounded-lg focus:outline-none"
            aria-label="Toggle navigation menu"
          >
            {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </header>

      {/* Desktop Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-72 bg-[#0D1322]/95 backdrop-blur-xl text-slate-300 flex flex-col border-r border-white/[0.08] transition-transform duration-300 ease-in-out md:translate-x-0 md:static md:h-screen
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Brand Header */}
        <div className="p-5 flex items-center justify-between border-b border-white/[0.08] bg-[#090D16]/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-glow-blue border border-blue-400/30">
              <Scale className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-white tracking-tight">LegalOS</h1>
                <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-blue-500/20 text-blue-300 border border-blue-400/30 uppercase">
                  v2.5 PRO
                </span>
              </div>
              <span className="text-[11px] text-slate-400 font-medium">Compliance & Risk OS</span>
            </div>
          </div>
        </div>

        {/* Enterprise Entity Context Badge */}
        <div className="px-4 pt-4 pb-2">
          <div className="p-2.5 rounded-lg bg-[#141C30]/80 border border-white/[0.06] flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <Building2 className="w-4 h-4 text-blue-400 shrink-0" />
              <div className="truncate">
                <div className="font-semibold text-slate-200 truncate text-[11px]">Acme Technologies Pvt Ltd</div>
                <div className="text-[10px] font-mono text-slate-400">ROC Delhi · Pvt Ltd</div>
              </div>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" title="Active Entity" />
          </div>
        </div>

        {/* Sidebar Nav */}
        <nav className="flex-1 px-3 py-3 space-y-1 overflow-y-auto">
          <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">
            Core Workspaces
          </div>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) => `
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 group
                  ${isActive 
                    ? 'bg-blue-600/20 text-blue-300 border border-blue-500/40 shadow-glow-blue font-semibold' 
                    : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200 border border-transparent'}
                `}
              >
                <Icon className="w-4 h-4 flex-shrink-0 transition-transform group-hover:scale-105" />
                <span className="flex-1 truncate">{item.name}</span>
              </NavLink>
            );
          })}

          <div className="pt-4 px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">
            Security & Audit
          </div>
          <div className="p-3 rounded-lg bg-[#090D16]/80 border border-white/[0.06] text-[11px] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">GSTIN API (Live):</span>
              <span className="text-emerald-400 font-mono font-semibold">200 OK (42ms)</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Vector Isolation:</span>
              <span className="text-blue-400 font-mono font-semibold">Qdrant Active</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Audit Trail:</span>
              <span className="text-slate-300 font-mono">100% Logged</span>
            </div>
          </div>
        </nav>

        {/* Desktop Actor switcher footer */}
        <div className="p-3 border-t border-white/[0.08] bg-[#090D16]/70">
          <RoleSwitcher />
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 md:h-screen md:overflow-y-auto">
        {/* Desktop Header with Dynamic Breadcrumbs & Telemetry */}
        <header className="hidden md:flex items-center justify-between bg-[#0D1322]/80 backdrop-blur-md border-b border-white/[0.08] px-8 py-3 sticky top-0 z-30 shadow-sm">
          {/* Breadcrumbs */}
          <nav className="flex items-center gap-2 text-xs font-medium text-slate-400" aria-label="Breadcrumb">
            {getBreadcrumbs().map((crumb, idx, arr) => (
              <React.Fragment key={crumb.href + idx}>
                {idx > 0 && <span className="text-slate-600">/</span>}
                {idx === arr.length - 1 ? (
                  <span className="font-semibold text-white tracking-tight">{crumb.label}</span>
                ) : (
                  <NavLink to={crumb.href} className="hover:text-blue-400 transition-colors">
                    {crumb.label}
                  </NavLink>
                )}
              </React.Fragment>
            ))}
          </nav>

          {/* Center Telemetry Banner */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-[#141C30] border border-amber-500/20 text-[11px] text-amber-300 font-mono shadow-xs">
            <Zap className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>Next Statutory Obligation: <strong>GST GSTR-3B</strong> in 3 Days (₹0 Penalty Risk)</span>
          </div>

          {/* Right Header Status Badges */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-950/60 text-emerald-300 border border-emerald-500/30 text-xs font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-glow-emerald" />
              <span>Compliance Posture: <strong>96.4% Audit-Ready</strong></span>
            </div>
          </div>
        </header>

        {/* Page Container */}
        <div className="flex-1 p-4 md:p-8 max-w-7xl w-full mx-auto">
          {children}
        </div>

        {/* Mobile Navigation bar */}
        <nav className="md:hidden fixed bottom-0 inset-x-0 bg-[#0D1322] border-t border-white/10 flex justify-around text-slate-400 py-2 z-30">
          {navigation.filter(n => n.active).map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) => `
                  flex flex-col items-center justify-center text-[10px] font-semibold
                  ${isActive ? 'text-blue-400' : 'text-slate-400 hover:text-slate-200'}
                `}
              >
                <Icon className="w-5 h-5" />
                <span className="mt-1">{item.shortName}</span>
              </NavLink>
            );
          })}
        </nav>
      </main>
    </div>
  );
};
export default AppShell;

