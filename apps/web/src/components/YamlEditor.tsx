"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Crosshair, FileCode2, RefreshCcw } from "lucide-react";

import type { ValidationIssue } from "@/lib/types";

function lineFromPath(path: string, lineCount: number): number | null {
  const match = path.match(/(?:line|yaml)\D+(\d+)/i);
  if (!match) {
    return null;
  }
  const line = Number(match[1]);
  if (!Number.isFinite(line) || line < 1) {
    return null;
  }
  return Math.min(line, Math.max(1, lineCount));
}

export function YamlEditor({
  value,
  onChange,
  issues = [],
  valid,
  onValidate,
  validating = false,
}: {
  value: string;
  onChange: (value: string) => void;
  issues?: ValidationIssue[];
  valid?: boolean;
  onValidate?: () => void;
  validating?: boolean;
}) {
  const [activeIssue, setActiveIssue] = useState<ValidationIssue | null>(null);
  const lines = useMemo(() => value.split("\n"), [value]);
  const lineCount = Math.max(1, lines.length);
  const characterCount = value.length;
  const activeLine = activeIssue ? lineFromPath(activeIssue.path, lineCount) : null;
  const issueCount = issues.length;

  return (
    <section className="yaml-editor-shell" aria-label="YAML 编辑器">
      <header className="yaml-editor-status">
        <div>
          <FileCode2 size={15} />
          <strong>YAML</strong>
          <span>{lineCount} 行</span>
          <span>{characterCount} 字符</span>
        </div>
        <div>
          {valid ? (
            <span className="yaml-state success">
              <CheckCircle2 size={14} />
              Schema 通过
            </span>
          ) : issueCount ? (
            <span className="yaml-state error">
              <AlertTriangle size={14} />
              {issueCount} 个问题
            </span>
          ) : (
            <span className="yaml-state neutral">等待校验</span>
          )}
          {onValidate && (
            <button className="btn-secondary compact" onClick={onValidate} disabled={validating || !value} type="button">
              <RefreshCcw size={14} className={validating ? "animate-spin" : ""} />
              校验
            </button>
          )}
        </div>
      </header>

      <div className="yaml-editor-grid">
        <pre className="yaml-line-numbers" aria-hidden="true">
          {Array.from({ length: lineCount }, (_, index) => {
            const line = index + 1;
            return (
              <span key={line} className={activeLine === line ? "active" : ""}>
                {line}
              </span>
            );
          })}
        </pre>
        <textarea
          className="yaml-textarea"
          spellCheck={false}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-label="YAML 文本"
        />
      </div>

      <aside className="yaml-diagnostics" aria-label="YAML 诊断">
        <div className="yaml-diagnostics-heading">
          <strong>诊断</strong>
          <span>{issueCount ? `${issueCount} 项` : "无问题"}</span>
        </div>
        {issues.length ? (
          issues.slice(0, 10).map((issue, index) => {
            const line = lineFromPath(issue.path, lineCount);
            const active = activeIssue?.path === issue.path && activeIssue?.message === issue.message;
            return (
              <button
                key={`${issue.path}-${issue.message}-${index}`}
                className={active ? "yaml-diagnostic active" : "yaml-diagnostic"}
                onClick={() => setActiveIssue(issue)}
                type="button"
              >
                <Crosshair size={14} />
                <span>{line ? `L${line}` : issue.severity}</span>
                <p>{issue.message}</p>
              </button>
            );
          })
        ) : (
          <p className="yaml-diagnostic-empty">Schema 校验通过后，问题会按路径显示在这里。</p>
        )}
      </aside>
    </section>
  );
}
