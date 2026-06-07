'use client';

import React from 'react';
import { Download } from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import ExportDialog from '@/components/ExportDialog';

export default function ExportPage() {
  const { project, chapters } = useProjectStore();

  if (chapters.length === 0) {
    return (
      <div className="flex items-center justify-center h-full" style={{ color: 'var(--color-muted)' }}>
        <div className="text-center">
          <Download size={48} className="mb-4 mx-auto" style={{ color: 'var(--color-border)' }} />
          <p className="text-lg">暂无可导出的内容</p>
          <p className="text-sm mt-2">等待Pipeline完成所有阶段后可导出</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6 animate-fade-in">
      <div className="text-center mb-6">
        <h1 className="text-xl font-bold" style={{ color: 'var(--color-foreground)' }}>
          导出中心
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--color-muted)' }}>
          将改编完成的剧本导出为多种格式
        </p>
      </div>

      {/* This page opens the ExportDialog directly */}
      {/* In practice, we embed the export functionality here */}
      <div className="panel text-center py-8">
        <Download size={32} className="mb-3 mx-auto" style={{ color: 'var(--color-accent)' }} />
        <p className="text-sm mb-2" style={{ color: 'var(--color-foreground)' }}>
          点击按钮打开导出面板
        </p>
        <p className="text-xs mb-4" style={{ color: 'var(--color-muted)' }}>
          支持 YAML / JSON / Markdown / Fountain / ZIP 五种格式
        </p>
      </div>
    </div>
  );
}