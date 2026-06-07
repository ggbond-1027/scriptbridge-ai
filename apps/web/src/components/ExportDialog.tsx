'use client';

import React, { useState } from 'react';
import {
  X,
  Download,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Archive,
  Code,
  BookOpen,
  FileQuestion,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { exportApi } from '@/lib/api';
import { ValidationError, ExportRequest } from '@/lib/types';

type ExportFormat = 'yaml' | 'json' | 'markdown' | 'fountain' | 'zip' | 'docs';

const FORMAT_INFO: Record<ExportFormat, { label: string; description: string; icon: React.ReactNode }> = {
  yaml: {
    label: 'YAML',
    description: '完整剧本数据结构，适合程序化处理和二次编辑',
    icon: <Code size={20} />,
  },
  json: {
    label: 'JSON',
    description: '标准JSON格式，适合前端集成和API对接',
    icon: <Code size={20} />,
  },
  markdown: {
    label: 'Markdown',
    description: '人类可读格式，适合审阅和文档化',
    icon: <FileText size={20} />,
  },
  fountain: {
    label: 'Fountain',
    description: '专业剧本格式，可直接导入Final Draft等工具',
    icon: <BookOpen size={20} />,
  },
  zip: {
    label: 'ZIP打包',
    description: '包含所有格式的完整导出包',
    icon: <Archive size={20} />,
  },
  docs: {
    label: '说明文档',
    description: '导出YAML Schema、Schema设计原因和机器校验Schema',
    icon: <FileQuestion size={20} />,
  },
};

interface ExportDialogProps {
  onClose: () => void;
}

export default function ExportDialog({ onClose }: ExportDialogProps) {
  const { validationErrors, project } = useProjectStore();
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('fountain');
  const [includeSourceRefs, setIncludeSourceRefs] = useState(true);
  const [includeMetadata, setIncludeMetadata] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportResult, setExportResult] = useState<{ download_url: string; filename: string; size_bytes: number } | null>(null);

  const hasErrors = validationErrors.filter((e) => e.severity === 'error').length > 0;
  const hasWarnings = validationErrors.filter((e) => e.severity === 'warning').length > 0;
  const isDocumentationExport = selectedFormat === 'docs';

  const handleExport = async () => {
    if (!project && !isDocumentationExport) return;
    setIsExporting(true);
    setExportResult(null);
    try {
      const result = isDocumentationExport
        ? await exportApi.exportDocumentation()
        : await exportApi.export(project!.id, {
            format: selectedFormat,
            include_source_refs: includeSourceRefs,
            include_metadata: includeMetadata,
          });
      setExportResult(result);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  const handleDownload = async () => {
    if (!exportResult) return;
    if (!project && !isDocumentationExport) return;
    const downloadUrl = isDocumentationExport
      ? await exportApi.getDocumentationDownloadUrl()
      : await exportApi.getDownloadUrl(project!.id, selectedFormat);
    window.open(downloadUrl, '_blank');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0"
        style={{ backgroundColor: 'oklch(0.10 0.02 260 / 0.8)' }}
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        className="relative panel z-10 max-h-[calc(100vh-24px)] w-[calc(100vw-24px)] max-w-[520px] overflow-auto sm:max-h-[calc(100vh-48px)]"
        style={{ backgroundColor: 'var(--color-surface)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-foreground)' }}>
            <Download size={18} style={{ color: 'var(--color-accent)' }} />
            导出中心
          </h2>
          <button onClick={onClose} style={{ color: 'var(--color-muted)' }}>
            <X size={18} />
          </button>
        </div>

        {/* Validation status */}
        {!isDocumentationExport && (
        <div className="mb-4">
          <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-muted)' }}>
            校验状态
          </h3>
          {hasErrors ? (
            <div
              className="flex items-center gap-2 p-3 rounded"
              style={{
                backgroundColor: 'oklch(0.65 0.18 25 / 0.1)',
                borderLeft: '3px solid var(--color-warning)',
              }}
            >
              <AlertTriangle size={16} style={{ color: 'var(--color-warning)' }} />
              <div>
                <p className="text-sm" style={{ color: 'var(--color-warning)' }}>
                  存在 {validationErrors.filter((e) => e.severity === 'error').length} 个校验错误
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
                  导出的剧本可能存在引用缺失或格式问题。建议先修复错误，或选择导出草稿。
                </p>
              </div>
            </div>
          ) : hasWarnings ? (
            <div
              className="flex items-center gap-2 p-3 rounded"
              style={{
                backgroundColor: 'oklch(0.75 0.15 75 / 0.1)',
                borderLeft: '3px solid var(--color-accent)',
              }}
            >
              <AlertTriangle size={16} style={{ color: 'var(--color-accent)' }} />
              <div>
                <p className="text-sm" style={{ color: 'var(--color-accent)' }}>
                  存在 {validationErrors.filter((e) => e.severity === 'warning').length} 个警告
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
                  建议检查警告内容，但不影响导出。
                </p>
              </div>
            </div>
          ) : (
            <div
              className="flex items-center gap-2 p-3 rounded"
              style={{
                backgroundColor: 'oklch(0.65 0.15 150 / 0.1)',
                borderLeft: '3px solid var(--color-teal)',
              }}
            >
              <CheckCircle2 size={16} style={{ color: 'var(--color-teal)' }} />
              <p className="text-sm" style={{ color: 'var(--color-teal)' }}>
                校验通过，可以安全导出
              </p>
            </div>
          )}
        </div>
        )}

        {/* Format selection */}
        <div className="mb-4">
          <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-muted)' }}>
            导出格式
          </h3>
          <div className="grid grid-cols-1 gap-2">
            {(Object.entries(FORMAT_INFO) as [ExportFormat, typeof FORMAT_INFO[ExportFormat]][]).map(
              ([format, info]) => (
                <button
                  key={format}
                  onClick={() => setSelectedFormat(format)}
                  aria-pressed={selectedFormat === format}
                  className="panel grid w-full grid-cols-[40px_minmax(0,1fr)] items-center gap-3 text-left transition-all"
                  style={{
                    borderColor: selectedFormat === format ? 'var(--color-accent)' : 'var(--color-border)',
                    borderWidth: '1px',
                    boxShadow: selectedFormat === format ? '0 0 0 1px var(--color-accent)' : 'none',
                  }}
                >
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded"
                    style={{
                      color: selectedFormat === format ? 'var(--color-accent)' : 'var(--color-muted)',
                      backgroundColor: selectedFormat === format
                        ? 'oklch(0.75 0.15 75 / 0.10)'
                        : 'oklch(0.90 0.01 260 / 0.04)',
                    }}
                  >
                    {info.icon}
                  </div>
                  <div className="min-w-0 text-left">
                    <span
                      className="block text-sm font-semibold"
                      style={{
                        color: selectedFormat === format ? 'var(--color-accent)' : 'var(--color-foreground)',
                      }}
                    >
                      {info.label}
                    </span>
                    <p className="mt-1 text-left text-xs leading-5" style={{ color: 'var(--color-muted)' }}>
                      {info.description}
                    </p>
                  </div>
                </button>
              )
            )}
          </div>
        </div>

        {/* Options */}
        {!isDocumentationExport && (
        <div className="mb-4">
          <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-muted)' }}>
            导出选项
          </h3>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={includeSourceRefs}
                onChange={(e) => setIncludeSourceRefs(e.target.checked)}
                style={{ accentColor: 'var(--color-accent)' }}
              />
              <span style={{ color: 'var(--color-foreground)' }}>包含来源引用 (source_ref)</span>
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={includeMetadata}
                onChange={(e) => setIncludeMetadata(e.target.checked)}
                style={{ accentColor: 'var(--color-accent)' }}
              />
              <span style={{ color: 'var(--color-foreground)' }}>包含生成元数据</span>
            </label>
          </div>
        </div>
        )}

        {/* Export button */}
        <div className="flex items-center gap-2">
          {hasErrors && !isDocumentationExport ? (
            <div className="flex-1">
              <button
                onClick={handleExport}
                disabled={isExporting}
                className="btn-accent w-full flex items-center justify-center gap-2"
              >
                {isExporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                导出草稿（含错误）
              </button>
              <p className="text-xs mt-1 text-center" style={{ color: 'var(--color-warning)' }}>
                草稿导出可能存在引用缺失
              </p>
            </div>
          ) : (
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="btn-accent flex-1 flex items-center justify-center gap-2"
            >
              {isExporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
              导出 {FORMAT_INFO[selectedFormat].label}
            </button>
          )}
          <button onClick={onClose} className="btn-ghost">
            取消
          </button>
        </div>

        {/* Export result */}
        {exportResult && (
          <div
            className="mt-4 p-3 rounded"
            style={{
              backgroundColor: 'oklch(0.65 0.15 150 / 0.1)',
              borderLeft: '3px solid var(--color-teal)',
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 size={14} style={{ color: 'var(--color-teal)' }} />
              <span className="text-sm" style={{ color: 'var(--color-teal)' }}>
                导出成功
              </span>
            </div>
            <div className="text-xs space-y-1" style={{ color: 'var(--color-muted)' }}>
              <div>文件名: {exportResult.filename}</div>
              <div>大小: {(exportResult.size_bytes / 1024).toFixed(1)} KB</div>
            </div>
            <button
              onClick={handleDownload}
              className="btn-accent text-sm mt-2 flex items-center gap-1"
            >
              <Download size={14} />
              下载文件
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
