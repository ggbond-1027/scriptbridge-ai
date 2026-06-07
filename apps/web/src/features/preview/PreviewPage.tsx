'use client';

import React from 'react';
import { BookOpen } from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import ScriptPreview from '@/components/ScriptPreview';

export default function PreviewPage() {
  const { project, chapters } = useProjectStore();

  if (chapters.length === 0) {
    return (
      <div className="flex items-center justify-center h-full" style={{ color: 'var(--color-muted)' }}>
        <div className="text-center">
          <BookOpen size={48} className="mb-4 mx-auto" style={{ color: 'var(--color-border)' }} />
          <p className="text-lg">暂无场景可预览</p>
          <p className="text-sm mt-2">等待Pipeline完成场景生成阶段</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden">
      <ScriptPreview />
    </div>
  );
}