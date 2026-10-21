import React from 'react';
import { AlertOctagon, AlertTriangle, ShieldCheck, HelpCircle } from 'lucide-react';

interface RiskBadgeProps {
  score: number;
  riskType?: string;
  className?: string;
  showScore?: boolean;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({
  score,
  riskType = 'none',
  className = '',
  showScore = true,
}) => {
  // Determine risk level based on score
  let level: 'low' | 'medium' | 'high' | 'none' = 'none';
  if (score > 0) {
    if (score < 30) level = 'low';
    else if (score < 70) level = 'medium';
    else level = 'high';
  } else if (riskType && riskType !== 'none') {
    level = 'low';
  }

  const styles = {
    high: {
      bg: 'bg-red-950/80 text-red-300 border-red-500/40 shadow-glow-ruby',
      icon: <AlertOctagon className="w-3.5 h-3.5 mr-1.5 text-red-400 shrink-0" aria-hidden="true" />,
      label: 'Critical Risk',
      dot: 'bg-red-500',
    },
    medium: {
      bg: 'bg-amber-950/80 text-amber-300 border-amber-500/40 shadow-glow-amber',
      icon: <AlertTriangle className="w-3.5 h-3.5 mr-1.5 text-amber-400 shrink-0" aria-hidden="true" />,
      label: 'Moderate Risk',
      dot: 'bg-amber-500',
    },
    low: {
      bg: 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40 shadow-glow-emerald',
      icon: <ShieldCheck className="w-3.5 h-3.5 mr-1.5 text-emerald-400 shrink-0" aria-hidden="true" />,
      label: 'Low Risk',
      dot: 'bg-emerald-500',
    },
    none: {
      bg: 'bg-slate-900 text-slate-400 border-white/10',
      icon: <HelpCircle className="w-3.5 h-3.5 mr-1.5 text-slate-400 shrink-0" aria-hidden="true" />,
      label: 'Unassessed',
      dot: 'bg-slate-500',
    },
  };

  const current = styles[level];

  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full border text-xs font-semibold backdrop-blur-sm ${current.bg} ${className}`}
      title={`Risk score: ${score}/100, Type: ${riskType}`}
    >
      {current.icon}
      <span>{current.label}</span>
      {showScore && (
        <span className="ml-1.5 font-mono text-[11px] opacity-80 font-bold tabular-nums">
          [{score}/100]
        </span>
      )}
    </span>
  );
};
export default RiskBadge;

