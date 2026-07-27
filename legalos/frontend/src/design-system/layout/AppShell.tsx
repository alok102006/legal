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
  Scale
} from 'lucide-react';
import { RoleSwitcher } from '@/lib/auth/AuthContext';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const navigation = [
    { name: 'Contract Intelligence', href: '/', icon: FileText, active: true },
    { name: 'Vendor Intelligence', href: '/vendors', icon: Users, active: true },
    { name: 'Legal Notice Center', href: '/notices', icon: Bell, active: true },
    { name: 'Compliance Center', href: '/compliance', icon: Activity, active: true },
    { name: 'Knowledge Hub', href: '/knowledge', icon: BookOpen, active: false, label: 'Phase 2' },
  ];

  const currentNav = navigation.find((item) => {
    if (item.href === '/') {
      return location.pathname === '/' || location.pathname.startsWith('/contracts');
    }
    return location.pathname.startsWith(item.href);
  });
  const activeTitle = currentNav ? `${currentNav.name} Workspace` : 'LegalOS Workspace';

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-50">
      {/* Mobile top bar header */}
      <header className="md:hidden flex items-center justify-between bg-slate-900 text-white px-4 py-3 shadow-md">
        <div className="flex items-center gap-2">
          <Scale className="w-6 h-6 text-blue-400" />
          <span className="font-bold text-lg tracking-tight">LegalOS</span>
        </div>
        <div className="flex items-center gap-2">
          <RoleSwitcher />
          <button 
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1 hover:bg-slate-800 rounded-md focus:outline-none"
            aria-label="Toggle navigation menu"
          >
            {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </header>

      {/* Desktop Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 transition-transform duration-300 ease-in-out md:translate-x-0 md:static md:h-screen
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="p-6 flex items-center gap-3 border-b border-slate-800 bg-slate-950">
          <Scale className="w-8 h-8 text-blue-500" />
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight leading-none">LegalOS</h1>
            <span className="text-[10px] text-slate-400 font-semibold tracking-wider uppercase mt-1 block">India SME Compliance</span>
          </div>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const Icon = item.icon;
            if (!item.active) {
              return (
                <div 
                  key={item.name}
                  className="flex items-center gap-3 px-3 py-2 text-slate-500 rounded-md text-sm font-medium cursor-not-allowed opacity-60"
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  <span className="flex-1">{item.name}</span>
                  <span className="text-[9px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400 border border-slate-700 font-semibold">{item.label}</span>
                </div>
              );
            }

            return (
              <NavLink
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) => `
                  flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors
                  ${isActive 
                    ? 'bg-blue-600 text-white shadow-sm' 
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'}
                `}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Desktop Actor switcher footer */}
        <div className="hidden md:block p-4 border-t border-slate-800 bg-slate-950">
          <RoleSwitcher />
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 md:h-screen md:overflow-y-auto">
        {/* Desktop Header */}
        <header className="hidden md:flex items-center justify-between bg-white border-b border-slate-200 px-8 py-4 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-800">
            {activeTitle}
          </h2>
          <div className="flex items-center gap-4">
            <span className="text-xs text-slate-500 font-medium">Production Build v1.0</span>
          </div>
        </header>

        {/* Page Container */}
        <div className="flex-1 p-4 md:p-8 max-w-7xl w-full mx-auto">
          {children}
        </div>

        {/* Mobile Navigation bar */}
        <nav className="md:hidden fixed bottom-0 inset-x-0 bg-slate-900 border-t border-slate-800 flex justify-around text-slate-400 py-2 z-30">
          {navigation.filter(n => n.active).map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) => `
                  flex flex-col items-center justify-center text-xs font-semibold
                  ${isActive ? 'text-blue-500' : 'text-slate-400'}
                `}
              >
                <Icon className="w-5 h-5" />
                <span className="mt-1">{item.name.split(' ')[0]}</span>
              </NavLink>
            );
          })}
        </nav>
      </main>
    </div>
  );
};
export default AppShell;
