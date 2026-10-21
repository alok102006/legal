import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'success' | 'warning' | 'danger' | 'neutral';
  className?: string;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'primary',
  className = '',
  size = 'md',
}) => {
  const sizeStyles = {
    sm: 'px-2 py-0.5 text-[10px]',
    md: 'px-2.5 py-0.5 text-xs',
  };
  
  const baseStyle = 'inline-flex items-center font-medium rounded-full border tracking-wide transition-colors';
  
  const variants = {
    primary: 'bg-blue-950/70 text-blue-300 border-blue-500/30',
    secondary: 'bg-indigo-950/70 text-indigo-300 border-indigo-500/30',
    success: 'bg-emerald-950/70 text-emerald-300 border-emerald-500/30 shadow-xs',
    warning: 'bg-amber-950/70 text-amber-300 border-amber-500/30 shadow-xs',
    danger: 'bg-red-950/70 text-red-300 border-red-500/30 shadow-xs',
    neutral: 'bg-white/[0.05] text-[#94A3B8] border-white/10',
  };

  return (
    <span className={`${baseStyle} ${sizeStyles[size]} ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};
export default Badge;

