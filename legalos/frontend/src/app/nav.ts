import { BellRing, BookOpen, CalendarCheck, FileText, Home, Settings, Store, type LucideIcon } from 'lucide-react';

export interface NavItem { to: string; label: string; icon: LucideIcon; end?: boolean; hint: string }

export const NAV: NavItem[] = [
  { to: '/', label: 'Home', icon: Home, end: true, hint: 'Overview of what needs attention' },
  { to: '/contracts', label: 'Contracts', icon: FileText, hint: 'Review a contract before you sign' },
  { to: '/vendors', label: 'Vendors', icon: Store, hint: 'Check a supplier before you pay' },
  { to: '/notices', label: 'Notices', icon: BellRing, hint: 'Understand a legal notice and reply' },
  { to: '/compliance', label: 'Compliance', icon: CalendarCheck, hint: 'Tax and company-law deadlines' },
  { to: '/documents', label: 'Documents', icon: BookOpen, hint: 'Ask questions about your company papers' },
  { to: '/settings', label: 'Settings', icon: Settings, hint: 'Company profile and system status' },
];

/** Page title for the top bar, from the current path. */
export function pageTitle(pathname: string): string {
  if (pathname === '/') return 'Home';
  const seg = pathname.split('/')[1];
  const item = NAV.find((n) => n.to === `/${seg}`);
  if (!item) return 'LegalOS';
  const parts = pathname.split('/').filter(Boolean);
  const isDetail = parts.length > 1 && !(seg === 'documents' && parts[1] === 'c');   // /documents/c/:id is a chat, not a document
  if (!isDetail) return item.label;
  return { contracts: 'Contract', vendors: 'Vendor', notices: 'Notice', documents: 'Document' }[seg] ?? item.label;
}
