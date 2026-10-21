import React from 'react';

interface SkeletonProps {
  variant?: 'line' | 'circle' | 'card' | 'table';
  className?: string;
  count?: number;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'line',
  className = '',
  count = 1,
}) => {
  const baseClass = 'bg-white/[0.06] animate-pulse rounded-md';

  if (variant === 'circle') {
    return <div className={`${baseClass} rounded-full ${className}`} />;
  }

  if (variant === 'card') {
    return (
      <div className={`border border-white/[0.08] rounded-xl p-5 bg-[#0D1322]/80 backdrop-blur-md flex flex-col gap-3 ${className}`}>
        <div className={`${baseClass} h-6 w-1/3`} />
        <div className={`${baseClass} h-4 w-2/3`} />
        <div className="flex flex-col gap-2 mt-2">
          <div className={`${baseClass} h-3 w-full`} />
          <div className={`${baseClass} h-3 w-full`} />
          <div className={`${baseClass} h-3 w-4/5`} />
        </div>
        <div className="flex justify-between items-center mt-4 pt-3 border-t border-white/[0.06]">
          <div className={`${baseClass} h-8 w-20`} />
          <div className={`${baseClass} h-5 w-24`} />
        </div>
      </div>
    );
  }

  if (variant === 'table') {
    return (
      <div className={`border border-white/[0.08] rounded-xl overflow-hidden bg-[#0D1322]/80 ${className}`}>
        <div className="bg-[#141C30]/80 border-b border-white/[0.06] p-4 flex gap-4">
          <div className={`${baseClass} h-4 w-12`} />
          <div className={`${baseClass} h-4 w-1/4`} />
          <div className={`${baseClass} h-4 w-1/6`} />
          <div className={`${baseClass} h-4 w-12`} />
        </div>
        <div className="p-4 flex flex-col gap-4">
          {Array.from({ length: count }).map((_, idx) => (
            <div key={idx} className="flex gap-4 items-center">
              <div className={`${baseClass} h-3 w-8`} />
              <div className={`${baseClass} h-3 w-1/3`} />
              <div className={`${baseClass} h-3 w-1/5`} />
              <div className={`${baseClass} h-3 w-16`} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 w-full">
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className={`${baseClass} h-4 ${idx === count - 1 && count > 1 ? 'w-4/5' : 'w-full'} ${className}`}
        />
      ))}
    </div>
  );
};
export default Skeleton;

