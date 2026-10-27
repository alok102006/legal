import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import * as Dialog from '@radix-ui/react-dialog';
import { FileText, Search, Store, BellRing, BookOpen, Upload, CalendarPlus, Sparkles } from 'lucide-react';
import { NAV } from './nav';
import { useContracts } from '@/features/contracts/api';
import { useVendors } from '@/features/vendors/api';
import { useNotices } from '@/features/notices/api';
import { useDocuments } from '@/features/documents/api';

export const CommandPalette: React.FC<{ open: boolean; onOpenChange: (o: boolean) => void }> = ({ open, onOpenChange }) => {
  const navigate = useNavigate();
  const contracts = useContracts();
  const vendors = useVendors();
  const notices = useNotices();
  const documents = useDocuments();
  const [q, setQ] = useState('');
  useEffect(() => { if (!open) setQ(''); }, [open]);

  const go = (to: string) => { onOpenChange(false); navigate(to); };
  const itemCls = 'flex min-h-[40px] cursor-pointer items-center gap-3 rounded-md px-3 text-sm text-ink data-[selected=true]:bg-primary-soft data-[selected=true]:text-primary-ink';
  const heading = 'px-3 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-ink-3';

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-[12vh] z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl animate-in" aria-label="Search and jump to">
          <Dialog.Title className="sr-only">Search LegalOS</Dialog.Title>
          <Command label="Search" loop>
            <div className="flex items-center gap-2 border-b border-line px-4">
              <Search className="h-4 w-4 text-ink-3" aria-hidden />
              <Command.Input value={q} onValueChange={setQ} placeholder="Search contracts, suppliers, notices, documents… or jump to a page" className="h-12 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3" />
              <kbd className="hidden rounded border border-line px-1.5 py-0.5 text-[10px] text-ink-3 sm:block">Esc</kbd>
            </div>
            <Command.List className="max-h-[60vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-8 text-center text-sm text-ink-2">Nothing matches. Try another word.</Command.Empty>
              <Command.Group heading="Actions" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-ink-3">
                <Command.Item className={itemCls} onSelect={() => go('/contracts?new=1')}><Upload className="h-4 w-4" aria-hidden />Review a new contract</Command.Item>
                <Command.Item className={itemCls} onSelect={() => go('/vendors?new=1')}><Store className="h-4 w-4" aria-hidden />Check a supplier</Command.Item>
                <Command.Item className={itemCls} onSelect={() => go('/notices?new=1')}><BellRing className="h-4 w-4" aria-hidden />Add a legal notice</Command.Item>
                <Command.Item className={itemCls} onSelect={() => go('/documents?ask=1')}><Sparkles className="h-4 w-4" aria-hidden />Ask my documents a question</Command.Item>
                <Command.Item className={itemCls} onSelect={() => go('/compliance?new=1')}><CalendarPlus className="h-4 w-4" aria-hidden />Add a compliance reminder</Command.Item>
              </Command.Group>
              <Command.Group heading="Pages" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-ink-3">
                {NAV.map((n) => <Command.Item key={n.to} value={`page ${n.label} ${n.hint}`} className={itemCls} onSelect={() => go(n.to)}><n.icon className="h-4 w-4" aria-hidden />{n.label}<span className="ml-auto text-xs text-ink-3">{n.hint}</span></Command.Item>)}
              </Command.Group>
              {(contracts.data?.length ?? 0) > 0 && (
                <Command.Group heading="Contracts" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-ink-3">
                  {contracts.data!.map((c) => <Command.Item key={c.id} value={`contract ${c.title} ${c.counterparty_name ?? ''}`} className={itemCls} onSelect={() => go(`/contracts/${c.id}`)}><FileText className="h-4 w-4" aria-hidden /><span className="truncate">{c.title || c.filename}</span>{c.counterparty_name && <span className="ml-auto truncate text-xs text-ink-3">{c.counterparty_name}</span>}</Command.Item>)}
                </Command.Group>
              )}
              {(vendors.data?.length ?? 0) > 0 && (
                <Command.Group heading="Suppliers" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-ink-3">
                  {vendors.data!.map((v) => <Command.Item key={v.id} value={`supplier ${v.name} ${v.gstin ?? ''}`} className={itemCls} onSelect={() => go(`/vendors/${v.id}`)}><Store className="h-4 w-4" aria-hidden /><span className="truncate">{v.name}</span>{v.gstin && <span className="ml-auto font-mono text-xs text-ink-3">{v.gstin}</span>}</Command.Item>)}
                </Command.Group>
              )}
              {(notices.data?.length ?? 0) > 0 && (
                <Command.Group heading="Notices" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-ink-3">
                  {notices.data!.map((n) => <Command.Item key={n.id} value={`notice ${n.title ?? ''} ${n.issuer_name ?? ''}`} className={itemCls} onSelect={() => go(`/notices/${n.id}`)}><BellRing className="h-4 w-4" aria-hidden /><span className="truncate">{n.title}</span></Command.Item>)}
                </Command.Group>
              )}
              {(documents.data?.length ?? 0) > 0 && (
                <Command.Group heading="Documents" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-ink-3">
                  {documents.data!.map((d) => <Command.Item key={d.id} value={`document ${d.title} ${d.doc_type ?? ''}`} className={itemCls} onSelect={() => go(`/documents/${d.id}`)}><BookOpen className="h-4 w-4" aria-hidden /><span className="truncate">{d.title}</span></Command.Item>)}
                </Command.Group>
              )}
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
