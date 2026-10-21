import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  className?: string;
  footer?: React.ReactNode;
  headerAction?: React.ReactNode;
  variant?: 'default' | 'subtle' | 'glow';
}

export const Card: React.FC<CardProps> = ({
  children,
  title,
  subtitle,
  className = '',
  footer,
  headerAction,
  variant = 'default',
}) => {
  const variantStyles = {
    default: 'bg-[#0D1322]/90 border-white/[0.08] shadow-glass-card backdrop-blur-md',
    subtle: 'bg-[#141C30]/70 border-white/[0.06] backdrop-blur-sm',
    glow: 'bg-[#0D1322]/95 border-blue-500/40 shadow-glow-blue backdrop-blur-md'
  };

  return (
    <div className={`rounded-xl border transition-all duration-200 overflow-hidden flex flex-col ${variantStyles[variant]} ${className}`}>
      {(title || subtitle || headerAction) && (
        <div className="px-5 py-4 border-b border-white/[0.06] flex items-center justify-between gap-4">
          <div>
            {title && <h3 className="text-base font-semibold leading-6 text-[#F8FAFC] tracking-tight">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-[#94A3B8]">{subtitle}</p>}
          </div>
          {headerAction && <div>{headerAction}</div>}
        </div>
      )}
      <div className="px-5 py-5 flex-1 text-[#DDE2F7]">{children}</div>
      {footer && (
        <div className="bg-[#090D16]/60 px-5 py-3 border-t border-white/[0.06] flex items-center justify-end text-xs text-[#94A3B8]">
          {footer}
        </div>
      )}
    </div>
  );
};
export default Card;

