'use client';

import React from 'react';
import {
  ArrowRight,
  ArrowLeft,
  Plus,
  Minus,
  FileText,
} from 'lucide-react';
import { DiffResult, DiffLine } from '@/lib/types';

interface DiffViewerProps {
  diff: DiffResult;
  onAccept?: () => void;
  onReject?: () => void;
}

export default function DiffViewer({ diff, onAccept, onReject }: DiffViewerProps) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold flex items-center gap-1" style={{ color: 'var(--color-accent)' }}>
          <FileText size={14} />
          改写对比
        </h3>
        <div className="flex items-center gap-2">
          <button onClick={onReject} className="btn-ghost text-xs flex items-center gap-1">
            <ArrowLeft size={12} />
            恢复原版
          </button>
          <button onClick={onAccept} className="btn-accent text-xs flex items-center gap-1">
            <ArrowRight size={12} />
            采用新版
          </button>
        </div>
      </div>

      {/* Side-by-side diff */}
      <div className="grid grid-cols-2 gap-2">
        {/* Before (original) */}
        <div>
          <div
            className="text-xs font-semibold p-2 rounded-t"
            style={{ backgroundColor: 'var(--color-surface)', color: 'var(--color-muted)' }}
          >
            原版
          </div>
          <div
            className="p-2 rounded-b font-mono text-xs overflow-auto"
            style={{ backgroundColor: 'var(--color-base)', maxHeight: '200px' }}
          >
            {diff.before.split('\n').map((line, i) => (
              <div key={i} style={{ color: 'var(--color-foreground)' }}>
                {line}
              </div>
            ))}
          </div>
        </div>

        {/* After (rewritten) */}
        <div>
          <div
            className="text-xs font-semibold p-2 rounded-t"
            style={{ backgroundColor: 'var(--color-surface)', color: 'var(--color-accent)' }}
          >
            改写版
          </div>
          <div
            className="p-2 rounded-b font-mono text-xs overflow-auto"
            style={{ backgroundColor: 'var(--color-base)', maxHeight: '200px' }}
          >
            {diff.after.split('\n').map((line, i) => (
              <div key={i} style={{ color: 'var(--color-foreground)' }}>
                {line}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Inline diff view */}
      <div>
        <h4 className="text-xs font-semibold mb-1" style={{ color: 'var(--color-muted)' }}>
          详细差异
        </h4>
        <div
          className="font-mono text-xs space-y-0.5 overflow-auto"
          style={{ maxHeight: '200px' }}
        >
          {diff.changes.map((change, i) => (
            <DiffLineView key={i} change={change} />
          ))}
        </div>
      </div>
    </div>
  );
}

function DiffLineView({ change }: { change: DiffLine }) {
  const colors = {
    add: {
      background: 'oklch(0.65 0.15 150 / 0.1)',
      color: 'var(--color-teal)',
      icon: <Plus size={10} />,
    },
    remove: {
      background: 'oklch(0.65 0.18 25 / 0.1)',
      color: 'var(--color-warning)',
      icon: <Minus size={10} />,
    },
    unchanged: {
      background: undefined,
      color: 'var(--color-muted)',
      icon: null,
    },
  };

  const style = colors[change.type];

  return (
    <div
      className="flex items-center gap-2 py-0.5 px-2"
      style={{
        backgroundColor: style.background,
        color: style.color,
      }}
    >
      {style.icon}
      <span className="flex-1">{change.content}</span>
    </div>
  );
}