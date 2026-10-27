import React from 'react';
import { cn } from '@/lib/utils';

/** The LegalOS mark: a balance drawn in a single stroke, in ink. */
export const LogoMark: React.FC<{ className?: string; size?: number }> = ({ className, size = 28 }) => (
  <span className={cn('inline-flex shrink-0 items-center justify-center text-ink', className)} style={{ width: size, height: size }} aria-hidden>
    <svg viewBox="0 0 64 64" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M32 10v44M16 20h32M18 20L8 40h20zM46 20L36 40h20zM20 54h24" />
    </svg>
  </span>
);

export const Wordmark: React.FC<{ className?: string }> = ({ className }) => (
  <span className={cn('font-semibold tracking-[-0.02em] text-ink', className)}>LegalOS</span>
);

export const Logo: React.FC<{ size?: number; className?: string; textClassName?: string }> = ({ size = 26, className, textClassName = 'text-[20px]' }) => (
  <span className={cn('inline-flex items-center gap-2', className)}>
    <LogoMark size={size} />
    <Wordmark className={textClassName} />
  </span>
);
