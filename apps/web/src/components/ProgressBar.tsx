'use client';

import React from 'react';

interface ProgressBarProps {
  value: number;
  max: number;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  accent?: boolean;
  label?: string;
  className?: string;
}

export default function ProgressBar({
  value,
  max,
  size = 'md',
  showLabel = false,
  accent = true,
  label,
  className = '',
}: ProgressBarProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  const heights = {
    xs: '2px',
    sm: '4px',
    md: '8px',
    lg: '16px',
  };

  const barColor = accent ? 'var(--color-accent)' : 'var(--color-teal)';
  const bgColor = 'var(--color-border)';
  const height = heights[size];

  return (
    <div className={className}>
      {/* Label */}
      {(showLabel || label) && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
            {label || `${percentage}%`}
          </span>
          {showLabel && (
            <span className="text-xs" style={{ color: 'var(--color-foreground)' }}>
              {percentage.toFixed(1)}%
            </span>
          )}
        </div>
      )}

      {/* Bar */}
      <div
        className="w-full rounded-full overflow-hidden"
        style={{
          height,
          backgroundColor: bgColor,
        }}
      >
        <div
          className="rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${percentage}%`,
            height,
            backgroundColor: percentage >= 100 ? 'var(--color-teal)' : barColor,
          }}
        />
      </div>
    </div>
  );
}