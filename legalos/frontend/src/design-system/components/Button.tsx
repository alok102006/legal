import React from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'emerald';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyle = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 select-none';
  
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm hover:shadow-glow-blue border border-blue-400/30',
    secondary: 'bg-[#141C30] hover:bg-[#1E293B] text-[#F8FAFC] border border-white/10 hover:border-white/20',
    outline: 'bg-transparent border border-white/15 hover:border-blue-400/50 text-[#DDE2F7] hover:bg-white/[0.04]',
    emerald: 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm hover:shadow-glow-emerald border border-emerald-400/30',
    danger: 'bg-red-950/80 hover:bg-red-900/90 text-red-300 border border-red-500/40 hover:shadow-glow-ruby',
    ghost: 'hover:bg-white/[0.06] text-[#94A3B8] hover:text-[#F8FAFC]',
  };

  const sizes = {
    sm: 'px-2.5 py-1.5 text-xs gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2.5',
  };

  return (
    <button
      className={`${baseStyle} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />}
      {children}
    </button>
  );
};
export default Button;

