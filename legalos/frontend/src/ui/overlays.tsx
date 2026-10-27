import React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';
import * as Tooltip from '@radix-ui/react-tooltip';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './primitives';

/* ------------------------------------------------------------------ Dialog */

export const Modal: React.FC<{
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}> = ({ open, onOpenChange, title, description, children, footer }) => (
  <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-3xl bg-surface p-6 shadow-float animate-scale-in [--origin:center]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Dialog.Title className="text-lg font-semibold text-ink">{title}</Dialog.Title>
            {description && <Dialog.Description className="mt-1 text-sm text-ink-2">{description}</Dialog.Description>}
          </div>
          <Dialog.Close asChild>
            <button className="rounded-md p-1.5 text-ink-2 hover:bg-surface-2" aria-label="Close"><X className="h-5 w-5" aria-hidden /></button>
          </Dialog.Close>
        </div>
        <div className="mt-4">{children}</div>
        {footer && <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div>}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
);

export const ConfirmDialog: React.FC<{
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
}> = ({ open, onOpenChange, title, description, confirmLabel, danger, loading, onConfirm }) => (
  <Modal
    open={open}
    onOpenChange={onOpenChange}
    title={title}
    description={description}
    footer={
      <>
        <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={loading}>Cancel</Button>
        <Button variant={danger ? 'danger' : 'primary'} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
      </>
    }
  >
    <span className="sr-only">Please confirm.</span>
  </Modal>
);

/* ------------------------------------------------------------------ Tabs */

export const TabsRoot = Tabs.Root;

export const TabList: React.FC<{ children: React.ReactNode; label: string; className?: string }> = ({ children, label, className }) => (
  <Tabs.List aria-label={label} className={cn('flex overflow-x-auto border-b border-line', className)}>
    {children}
  </Tabs.List>
);

export const TabTrigger: React.FC<{ value: string; children: React.ReactNode; count?: number }> = ({ value, children, count }) => (
  <Tabs.Trigger
    value={value}
    className={cn(
      'relative -mb-px flex min-h-[44px] shrink-0 items-center gap-2 border-b-2 border-transparent px-1 py-2.5 text-[15px] font-medium text-ink-2 transition-colors first:ml-0',
      'mr-5 hover:text-ink data-[state=active]:border-ink data-[state=active]:text-ink',
    )}
  >
    {children}
    {count !== undefined && (
      <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs font-semibold text-ink-2">{count}</span>
    )}
  </Tabs.Trigger>
);

export const TabPanel: React.FC<{ value: string; children: React.ReactNode; className?: string }> = ({ value, children, className }) => (
  <Tabs.Content value={value} className={cn('pt-5 focus-visible:outline-none', className)}>{children}</Tabs.Content>
);

/* ------------------------------------------------------------------ Tooltip */

export const TooltipProviderRoot = Tooltip.Provider;

export const Hint: React.FC<{ text: string; children: React.ReactNode }> = ({ text, children }) => (
  <Tooltip.Root delayDuration={200}>
    <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
    <Tooltip.Portal>
      <Tooltip.Content
        sideOffset={6}
        className="z-50 max-w-xs rounded-lg bg-ink px-3 py-2 text-xs text-app shadow-lg"
      >
        {text}
        <Tooltip.Arrow className="fill-[var(--text)]" />
      </Tooltip.Content>
    </Tooltip.Portal>
  </Tooltip.Root>
);
