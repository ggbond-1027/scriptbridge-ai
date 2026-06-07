'use client';

import React, { useState, useMemo, useCallback, useRef } from 'react';
import {
  X,
  Plus,
  Trash2,
  RefreshCw,
  Target,
  Swords,
  MapPin,
  Clock,
  Users,
  Link,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Loader2,
  BookOpen,
  Undo2,
  Redo2,
  Search,
  Plus as PlusIcon,
  Minus,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { Scene, Element, ElementType, SourceRef, DiffLine } from '@/lib/types';
import { getElementTypeLabel, getElementTypeMarker } from '@/lib/fountain-render';

const ELEMENT_TYPES: ElementType[] = [
  'action',
  'dialogue',
  'parenthetical',
  'transition',
  'voice_over',
  'shot',
  'note',
];

interface SceneEditorProps {
  scene?: Scene;
  onClose?: () => void;
}

/* === Edit Snapshot for Undo/Redo === */
interface EditSnapshot {
  title: string;
  purpose: string;
  conflict: string;
  beats: string[];
}

/* === Rewrite Phase === */
type RewritePhase = 'instruction' | 'loading' | 'diff';

/* === Simple inline diff computation === */
function computeInlineDiff(before: string, after: string): DiffLine[] {
  const beforeLines = before.split('\n');
  const afterLines = after.split('\n');

  // Simple LCS-style diff: iterate through both texts character-by-character
  // For line-level diff, we do a basic comparison
  const result: DiffLine[] = [];

  // Use a simple approach: find common prefix, then diff the rest
  const maxLen = Math.max(beforeLines.length, afterLines.length);
  let bi = 0;
  let ai = 0;

  while (bi < beforeLines.length || ai < afterLines.length) {
    const bLine = bi < beforeLines.length ? beforeLines[bi] : undefined;
    const aLine = ai < afterLines.length ? afterLines[ai] : undefined;

    if (bLine === aLine) {
      result.push({ type: 'unchanged', content: bLine! });
      bi++;
      ai++;
    } else {
      // Look ahead in afterLines to see if bLine appears later (indicating additions)
      const bInAfter = aLine !== undefined ? afterLines.indexOf(bLine!, ai + 1) : -1;
      const aInBefore = bLine !== undefined ? beforeLines.indexOf(aLine!, bi + 1) : -1;

      if (bInAfter !== -1 && (aInBefore === -1 || bInAfter - ai <= aInBefore - bi)) {
        // Lines were added before bLine
        for (let k = ai; k < bInAfter; k++) {
          result.push({ type: 'add', content: afterLines[k] });
        }
        result.push({ type: 'unchanged', content: bLine! });
        bi++;
        ai = bInAfter + 1;
      } else if (aInBefore !== -1) {
        // Lines were removed before aLine
        for (let k = bi; k < aInBefore; k++) {
          result.push({ type: 'remove', content: beforeLines[k] });
        }
        result.push({ type: 'unchanged', content: aLine! });
        ai++;
        bi = aInBefore + 1;
      } else {
        // No match found - show as replace
        if (bLine !== undefined) {
          result.push({ type: 'remove', content: bLine });
          bi++;
        }
        if (aLine !== undefined) {
          result.push({ type: 'add', content: aLine });
          ai++;
        }
      }
    }
  }

  return result;
}

export default function SceneEditor({ scene, onClose }: SceneEditorProps) {
  const {
    chapters,
    selectedChapterId,
    selectedSceneId,
    project,
    updateScene,
    rewriteElement,
    selectParagraph,
    selectScene,
  } = useProjectStore();

  // Find the selected scene
  const currentScene = scene || (() => {
    const chapter = chapters.find((ch) => ch.id === selectedChapterId);
    return chapter?.scenes.find((sc) => sc.id === selectedSceneId);
  })();

  // Compute chapter context for scene navigation
  const chapterContext = useMemo(() => {
    if (!currentScene) return null;
    const currentChapter = chapters.find((ch) => ch.id === currentScene.chapter_id);
    if (!currentChapter) return null;

    const sortedScenes = [...currentChapter.scenes].sort(
      (a, b) => a.order_in_chapter - b.order_in_chapter
    );
    const currentSceneIndex = sortedScenes.findIndex(
      (sc) => sc.id === currentScene.id
    );

    const prevScene = currentSceneIndex > 0 ? sortedScenes[currentSceneIndex - 1] : null;
    const nextScene =
      currentSceneIndex < sortedScenes.length - 1 ? sortedScenes[currentSceneIndex + 1] : null;

    return {
      chapterTitle: currentChapter.title,
      chapterNumber: currentChapter.number,
      scenePosition: currentSceneIndex + 1,
      totalScenes: sortedScenes.length,
      prevScene,
      nextScene,
    };
  }, [currentScene, chapters]);

  // === Edit state ===
  const initialBeats = Array.isArray(currentScene?.beats)
    ? currentScene.beats
    : (typeof currentScene?.beats === 'string' && currentScene?.beats ? [currentScene.beats] : []);
  const initialSnapshot: EditSnapshot = {
    title: currentScene?.title || '',
    purpose: currentScene?.dramatic_purpose || '',
    conflict: currentScene?.conflict || '',
    beats: initialBeats,
  };

  const [editTitle, setEditTitle] = useState(initialSnapshot.title);
  const [editPurpose, setEditPurpose] = useState(initialSnapshot.purpose);
  const [editConflict, setEditConflict] = useState(initialSnapshot.conflict);
  const [editBeats, setEditBeats] = useState<string[]>(initialSnapshot.beats);
  const [expandedElements, setExpandedElements] = useState<Set<string>>(new Set());

  // === Undo/Redo state ===
  const [editHistory, setEditHistory] = useState<EditSnapshot[]>([initialSnapshot]);
  const [editHistoryIndex, setEditHistoryIndex] = useState(0);
  const historyIndexRef = useRef(0);

  // === Find/Replace state ===
  const [showFindReplace, setShowFindReplace] = useState(false);
  const [findText, setFindText] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [findMatchCount, setFindMatchCount] = useState(0);

  // === Rewrite state ===
  const [rewritingElement, setRewritingElement] = useState<string | null>(null);
  const [rewriteInstruction, setRewriteInstruction] = useState('');
  const [showRewriteDialog, setShowRewriteDialog] = useState<string | null>(null);
  const [rewritePhase, setRewritePhase] = useState<RewritePhase>('instruction');
  const [rewriteOriginalContent, setRewriteOriginalContent] = useState('');
  const [rewriteNewContent, setRewriteNewContent] = useState('');
  const [rewriteDiffLines, setRewriteDiffLines] = useState<DiffLine[]>([]);

  if (!currentScene) {
    return (
      <div className="text-center py-8" style={{ color: 'var(--color-muted)' }}>
        <p className="text-sm">选择场景进行编辑</p>
      </div>
    );
  }

  // === Undo/Redo helpers ===
  const pushEditSnapshot = useCallback((snapshot: EditSnapshot) => {
    const currentIndex = historyIndexRef.current;
    setEditHistory(prev => prev.slice(0, currentIndex + 1).concat([snapshot]));
    const newIndex = currentIndex + 1;
    setEditHistoryIndex(newIndex);
    historyIndexRef.current = newIndex;
  }, []);

  const handleUndo = useCallback(() => {
    const currentIndex = historyIndexRef.current;
    if (currentIndex > 0) {
      const newIndex = currentIndex - 1;
      // Read snapshot from editHistory state (synchronously available)
      const snapshot = editHistory[newIndex];
      if (snapshot) {
        setEditTitle(snapshot.title);
        setEditPurpose(snapshot.purpose);
        setEditConflict(snapshot.conflict);
        setEditBeats(snapshot.beats);
        setEditHistoryIndex(newIndex);
        historyIndexRef.current = newIndex;
      }
    }
  }, [editHistory]);

  const handleRedo = useCallback(() => {
    const currentIndex = historyIndexRef.current;
    if (currentIndex < editHistory.length - 1) {
      const newIndex = currentIndex + 1;
      const snapshot = editHistory[newIndex];
      if (snapshot) {
        setEditTitle(snapshot.title);
        setEditPurpose(snapshot.purpose);
        setEditConflict(snapshot.conflict);
        setEditBeats(snapshot.beats);
        setEditHistoryIndex(newIndex);
        historyIndexRef.current = newIndex;
      }
    }
  }, [editHistory]);

  // === Find/Replace helpers ===
  const getAllTextContent = useCallback(() => {
    const parts: string[] = [];
    if (editTitle) parts.push(editTitle);
    if (editPurpose) parts.push(editPurpose);
    if (editConflict) parts.push(editConflict);
    editBeats.forEach(b => { if (b) parts.push(b); });
    currentScene.elements.forEach(el => { if (el.content) parts.push(el.content); });
    return parts.join('\n');
  }, [editTitle, editPurpose, editConflict, editBeats, currentScene.elements]);

  const handleFind = useCallback(() => {
    if (!findText) {
      setFindMatchCount(0);
      return;
    }
    const allContent = getAllTextContent();
    const matches = allContent.split(findText).length - 1;
    setFindMatchCount(matches);
  }, [findText, getAllTextContent]);

  const handleReplace = useCallback(() => {
    if (!findText) return;
    // Replace in the first field that contains the find text
    if (editTitle.includes(findText)) {
      const newTitle = editTitle.replace(findText, replaceText);
      setEditTitle(newTitle);
      pushEditSnapshot({ title: newTitle, purpose: editPurpose, conflict: editConflict, beats: editBeats });
    } else if (editPurpose.includes(findText)) {
      const newPurpose = editPurpose.replace(findText, replaceText);
      setEditPurpose(newPurpose);
      pushEditSnapshot({ title: editTitle, purpose: newPurpose, conflict: editConflict, beats: editBeats });
    } else if (editConflict.includes(findText)) {
      const newConflict = editConflict.replace(findText, replaceText);
      setEditConflict(newConflict);
      pushEditSnapshot({ title: editTitle, purpose: editPurpose, conflict: newConflict, beats: editBeats });
    } else {
      // Check beats
      const newBeats = editBeats.map(b => b.includes(findText) ? b.replace(findText, replaceText) : b);
      if (newBeats.some((b, i) => b !== editBeats[i])) {
        setEditBeats(newBeats);
        pushEditSnapshot({ title: editTitle, purpose: editPurpose, conflict: editConflict, beats: newBeats });
      }
    }
    handleFind();
  }, [findText, replaceText, editTitle, editPurpose, editConflict, editBeats, pushEditSnapshot, handleFind]);

  const handleReplaceAll = useCallback(() => {
    if (!findText) return;
    let changed = false;
    let newTitle = editTitle;
    let newPurpose = editPurpose;
    let newConflict = editConflict;
    let newBeats = [...editBeats];

    if (editTitle.includes(findText)) {
      newTitle = editTitle.split(findText).join(replaceText);
      changed = true;
    }
    if (editPurpose.includes(findText)) {
      newPurpose = editPurpose.split(findText).join(replaceText);
      changed = true;
    }
    if (editConflict.includes(findText)) {
      newConflict = editConflict.split(findText).join(replaceText);
      changed = true;
    }
    newBeats = editBeats.map(b => b.includes(findText) ? b.split(findText).join(replaceText) : b);
    if (newBeats.some((b, i) => b !== editBeats[i])) changed = true;

    if (changed) {
      setEditTitle(newTitle);
      setEditPurpose(newPurpose);
      setEditConflict(newConflict);
      setEditBeats(newBeats);
      pushEditSnapshot({ title: newTitle, purpose: newPurpose, conflict: newConflict, beats: newBeats });
    }
    handleFind();
  }, [findText, replaceText, editTitle, editPurpose, editConflict, editBeats, pushEditSnapshot, handleFind]);

  // === Save handler ===
  const handleSave = async () => {
    if (!project) return;
    await updateScene(project.id, currentScene.id, {
      title: editTitle,
      dramatic_purpose: editPurpose,
      conflict: editConflict,
      beats: editBeats,
    });
  };

  // === Rewrite handler (enhanced with feedback) ===
  const handleRewrite = async (elementId: string) => {
    if (!project) return;

    // Save original content before rewriting
    const element = currentScene.elements.find(el => el.id === elementId);
    if (!element) return;
    const originalContent = element.content;
    setRewriteOriginalContent(originalContent);
    setRewritePhase('loading');
    setRewritingElement(elementId);

    try {
      // Call the store's rewriteElement (which updates the store)
      await rewriteElement(project.id, currentScene.id, elementId, rewriteInstruction);

      // After rewrite, read the new content from the updated scene in the store
      const updatedChapters = useProjectStore.getState().chapters;
      const updatedChapter = updatedChapters.find(ch => ch.id === currentScene.chapter_id);
      const updatedScene = updatedChapter?.scenes.find(sc => sc.id === currentScene.id);
      const updatedElement = updatedScene?.elements.find(el => el.id === elementId);
      const newContent = updatedElement?.content || '';

      // Revert the store back to original content (so user sees original while reviewing diff)
      const revertedChapters = updatedChapters.map(ch => ({
        ...ch,
        scenes: ch.scenes.map(sc => {
          if (sc.id === currentScene.id) {
            return {
              ...sc,
              elements: sc.elements.map(el =>
                el.id === elementId ? { ...el, content: originalContent } : el
              ),
            };
          }
          return sc;
        }),
      }));
      useProjectStore.setState({ chapters: revertedChapters });

      // Compute diff and transition to diff phase
      const diffLines = computeInlineDiff(originalContent, newContent);
      setRewriteNewContent(newContent);
      setRewriteDiffLines(diffLines);
      setRewritingElement(null);
      setRewritePhase('diff');
    } catch (err) {
      setRewritingElement(null);
      setRewritePhase('instruction');
      setShowRewriteDialog(null);
    }
  };

  // === Rewrite accept/reject handlers ===
  const handleAcceptRewrite = () => {
    const elementId = showRewriteDialog;
    if (!elementId) return;

    // Update the store with the new content
    const { chapters: currentChapters } = useProjectStore.getState();
    const updatedChapters = currentChapters.map(ch => ({
      ...ch,
      scenes: ch.scenes.map(sc => {
        if (sc.id === currentScene.id) {
          return {
            ...sc,
            elements: sc.elements.map(el =>
              el.id === elementId ? { ...el, content: rewriteNewContent } : el
            ),
          };
        }
        return sc;
      }),
    }));
    useProjectStore.setState({ chapters: updatedChapters });

    // Close dialog and reset state
    setShowRewriteDialog(null);
    setRewritePhase('instruction');
    setRewriteInstruction('');
    setRewriteOriginalContent('');
    setRewriteNewContent('');
    setRewriteDiffLines([]);
  };

  const handleRejectRewrite = () => {
    // Original content is already in the store (we reverted it earlier)
    // Just close dialog and reset state
    setShowRewriteDialog(null);
    setRewritePhase('instruction');
    setRewriteInstruction('');
    setRewriteOriginalContent('');
    setRewriteNewContent('');
    setRewriteDiffLines([]);
  };

  const handleSourceRefClick = (ref: SourceRef) => {
    selectParagraph(ref.paragraph_index);
  };

  const addBeat = () => {
    setEditBeats([...editBeats, '']);
  };

  const removeBeat = (index: number) => {
    setEditBeats(editBeats.filter((_, i) => i !== index));
  };

  const updateBeat = (index: number, value: string) => {
    const newBeats = editBeats.map((b, i) => (i === index ? value : b));
    setEditBeats(newBeats);
  };

  const toggleElement = (elementId: string) => {
    setExpandedElements((prev) => {
      const next = new Set(prev);
      if (next.has(elementId)) next.delete(elementId);
      else next.add(elementId);
      return next;
    });
  };

  // Wrapper setters that push to history
  const setTitleWithHistory = (value: string) => {
    setEditTitle(value);
    pushEditSnapshot({ title: value, purpose: editPurpose, conflict: editConflict, beats: editBeats });
  };
  const setPurposeWithHistory = (value: string) => {
    setEditPurpose(value);
    pushEditSnapshot({ title: editTitle, purpose: value, conflict: editConflict, beats: editBeats });
  };
  const setConflictWithHistory = (value: string) => {
    setEditConflict(value);
    pushEditSnapshot({ title: editTitle, purpose: editPurpose, conflict: value, beats: editBeats });
  };
  const updateBeatWithHistory = (index: number, value: string) => {
    const newBeats = editBeats.map((b, i) => (i === index ? value : b));
    setEditBeats(newBeats);
    pushEditSnapshot({ title: editTitle, purpose: editPurpose, conflict: editConflict, beats: newBeats });
  };

  return (
    <div className="space-y-4">
      {/* Close button (when opened as full editor) */}
      {onClose && (
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--color-foreground)' }}>
            场景编辑
          </h2>
          <button onClick={onClose} style={{ color: 'var(--color-muted)' }}>
            <X size={18} />
          </button>
        </div>
      )}

      {/* Scene heading info */}
      <div className="panel">
        {/* Chapter context bar */}
        {chapterContext && (
          <div
            className="flex items-center gap-2 mb-3 px-2 py-1.5 rounded"
            style={{ backgroundColor: 'var(--color-base)' }}
          >
            <BookOpen size={14} style={{ color: 'var(--color-teal)' }} />
            <span className="text-xs font-medium" style={{ color: 'var(--color-teal)' }}>
              第{chapterContext.chapterNumber}章 {chapterContext.chapterTitle}
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded-full"
              style={{ backgroundColor: 'oklch(0.55 0.08 260 / 0.08)', color: 'var(--color-accent)' }}
            >
              第{chapterContext.scenePosition}场 / 共{chapterContext.totalScenes}场
            </span>
            <div className="flex items-center gap-1 ml-auto">
              {chapterContext.prevScene ? (
                <button
                  className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded transition-colors hover:bg-surfaceHover"
                  style={{ color: 'var(--color-accent)' }}
                  onClick={() => selectScene(chapterContext.prevScene!.id)}
                  title={chapterContext.prevScene.title || `场景${chapterContext.prevScene.order_in_chapter}`}
                >
                  <ChevronLeft size={12} />
                  上一场
                </button>
              ) : (
                <span className="text-xs" style={{ color: 'var(--color-border)' }}>
                  无上一场
                </span>
              )}
              <span className="text-xs" style={{ color: 'var(--color-border)' }}>|</span>
              {chapterContext.nextScene ? (
                <button
                  className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded transition-colors hover:bg-surfaceHover"
                  style={{ color: 'var(--color-accent)' }}
                  onClick={() => selectScene(chapterContext.nextScene!.id)}
                  title={chapterContext.nextScene.title || `场景${chapterContext.nextScene.order_in_chapter}`}
                >
                  下一场
                  <ChevronRight size={12} />
                </button>
              ) : (
                <span className="text-xs" style={{ color: 'var(--color-border)' }}>
                  无下一场
                </span>
              )}
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 mb-2 text-xs">
          <MapPin size={12} style={{ color: 'var(--color-accent)' }} />
          <span style={{ color: 'var(--color-foreground)' }}>
            {currentScene.heading.context} {currentScene.heading.location_id}
          </span>
          <Clock size={12} style={{ color: 'var(--color-muted)' }} />
          <span style={{ color: 'var(--color-muted)' }}>
            {currentScene.heading.time_of_day}
          </span>
        </div>

        {/* === Editor Toolbar === */}
        <div
          className="flex items-center gap-1 mb-3 py-1.5 px-2 rounded"
          style={{ backgroundColor: 'var(--color-base)' }}
        >
          {/* Undo */}
          <button
            onClick={handleUndo}
            disabled={editHistoryIndex <= 0}
            className="p-1 rounded transition-colors hover:bg-surfaceHover disabled:opacity-30"
            style={{ color: 'var(--color-muted)' }}
            title="撤销"
          >
            <Undo2 size={14} />
          </button>

          {/* Redo */}
          <button
            onClick={handleRedo}
            disabled={editHistoryIndex >= editHistory.length - 1}
            className="p-1 rounded transition-colors hover:bg-surfaceHover disabled:opacity-30"
            style={{ color: 'var(--color-muted)' }}
            title="重做"
          >
            <Redo2 size={14} />
          </button>

          {/* Separator */}
          <div
            className="mx-1 h-4"
            style={{ borderLeft: '1px solid var(--color-border)' }}
          />

          {/* Find/Replace toggle */}
          <button
            onClick={() => {
              setShowFindReplace(!showFindReplace);
              if (showFindReplace) {
                setFindText('');
                setReplaceText('');
                setFindMatchCount(0);
              }
            }}
            className={`p-1 rounded transition-colors hover:bg-surfaceHover ${showFindReplace ? 'bg-surfaceHover' : ''}`}
            style={{ color: showFindReplace ? 'var(--color-accent)' : 'var(--color-muted)' }}
            title="查找/替换"
          >
            <Search size={14} />
          </button>

          {/* History indicator */}
          <span className="text-xs ml-auto" style={{ color: 'var(--color-border)' }}>
            {editHistoryIndex + 1}/{editHistory.length}
          </span>
        </div>

        {/* === Find/Replace Bar === */}
        {showFindReplace && (
          <div
            className="mb-3 p-2 rounded space-y-2"
            style={{ backgroundColor: 'oklch(0.55 0.08 260 / 0.06)' }}
          >
            <div className="flex items-center gap-2">
              <input
                type="text"
                className="input-field text-xs flex-1"
                placeholder="查找内容..."
                value={findText}
                onChange={(e) => {
                  const newFindText = e.target.value;
                  setFindText(newFindText);
                  // Compute match count immediately with the new value
                  if (newFindText) {
                    const allContent = getAllTextContent();
                    const matches = allContent.split(newFindText).length - 1;
                    setFindMatchCount(matches);
                  } else {
                    setFindMatchCount(0);
                  }
                }}
              />
              {findMatchCount > 0 && (
                <span className="text-xs shrink-0" style={{ color: 'var(--color-accent)' }}>
                  {findMatchCount}处匹配
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                className="input-field text-xs flex-1"
                placeholder="替换为..."
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
              />
              <button
                onClick={handleReplace}
                disabled={!findText}
                className="btn-ghost text-xs shrink-0"
              >
                替换
              </button>
              <button
                onClick={handleReplaceAll}
                disabled={!findText}
                className="btn-accent text-xs shrink-0"
              >
                全部替换
              </button>
            </div>
          </div>
        )}

        {/* Title edit */}
        <div className="mb-3">
          <label className="text-xs font-medium block mb-1" style={{ color: 'var(--color-muted)' }}>
            场景标题
          </label>
          <input
            type="text"
            className="input-field text-sm"
            value={editTitle}
            onChange={(e) => setTitleWithHistory(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 mb-3">
          {/* Dramatic purpose edit */}
          <div className="min-w-0">
            <label className="text-xs font-medium flex items-center gap-1 mb-1" style={{ color: 'var(--color-accent)' }}>
              <Target size={12} />
              戏剧目的
            </label>
            <textarea
              className="textarea-field text-sm resize-none overflow-hidden"
              rows={1}
              value={editPurpose}
              onChange={(e) => {
                setPurposeWithHistory(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = e.target.scrollHeight + 'px';
              }}
              ref={(el) => {
                if (el) {
                  el.style.height = 'auto';
                  el.style.height = el.scrollHeight + 'px';
                }
              }}
            />
          </div>

          {/* Conflict edit */}
          <div className="min-w-0">
            <label className="text-xs font-medium flex items-center gap-1 mb-1" style={{ color: 'var(--color-warning)' }}>
              <Swords size={12} />
              冲突
            </label>
            <textarea
              className="textarea-field text-sm resize-none overflow-hidden"
              rows={1}
              value={editConflict}
              onChange={(e) => {
                setConflictWithHistory(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = e.target.scrollHeight + 'px';
              }}
              ref={(el) => {
                if (el) {
                  el.style.height = 'auto';
                  el.style.height = el.scrollHeight + 'px';
                }
              }}
            />
          </div>
        </div>
      </div>

      {/* Beats section */}
      <div className="panel">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold" style={{ color: 'var(--color-accent)' }}>
            节拍 (Beats)
          </h3>
          <button
            onClick={addBeat}
            className="flex items-center gap-1 text-xs"
            style={{ color: 'var(--color-accent)' }}
          >
            <Plus size={12} />
            添加
          </button>
        </div>
        <div className="space-y-2">
          {editBeats.map((beat, index) => (
            <div key={index} className="flex items-center gap-2">
              <span
                className="text-xs shrink-0 w-4"
                style={{ color: 'var(--color-muted)' }}
              >
                {index + 1}
              </span>
              <input
                type="text"
                className="input-field text-xs flex-1"
                value={beat}
                onChange={(e) => updateBeatWithHistory(index, e.target.value)}
              />
              <button
                onClick={() => removeBeat(index)}
                className="shrink-0"
                style={{ color: 'var(--color-warning)' }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          {editBeats.length === 0 && (
            <p className="text-xs" style={{ color: 'var(--color-muted)' }}>暂无节拍</p>
          )}
        </div>
      </div>

      {/* Elements section */}
      <div className="panel">
        <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-accent)' }}>
          剧本元素 ({currentScene.elements.length})
        </h3>

        <div className="space-y-2">
          {currentScene.elements.map((element) => (
            <ElementEditor
              key={element.id}
              element={element}
              isExpanded={expandedElements.has(element.id)}
              isRewriting={rewritingElement === element.id}
              onToggle={() => toggleElement(element.id)}
              onRewrite={() => {
                setShowRewriteDialog(element.id);
                setRewritePhase('instruction');
                setRewriteInstruction('');
              }}
              onSourceRefClick={handleSourceRefClick}
            />
          ))}
        </div>

        {/* Add element */}
        <div className="flex items-center gap-2 mt-3">
          <button className="btn-ghost text-xs flex items-center gap-1">
            <Plus size={12} />
            添加元素
          </button>
        </div>
      </div>

      {/* Source references */}
      {currentScene.source_refs.length > 0 && (
        <div className="panel">
          <h3 className="text-xs font-semibold mb-2 flex items-center gap-1" style={{ color: 'var(--color-accent)' }}>
            <Link size={12} />
            来源引用 ({currentScene.source_refs.length})
          </h3>
          <div className="space-y-1">
            {currentScene.source_refs.map((ref, index) => (
              <button
                key={index}
                className="flex items-center gap-2 text-xs p-1 rounded hover:bg-surfaceHover w-full text-left transition-colors"
                style={{ color: 'var(--color-muted)' }}
                onClick={() => handleSourceRefClick(ref)}
              >
                <span style={{ color: 'var(--color-accent-dim)' }}>段{ref.paragraph_index}</span>
                {ref.text_preview && (
                  <span className="truncate">{ref.text_preview}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Save button */}
      <div className="flex items-center gap-2">
        <button onClick={handleSave} className="btn-accent text-sm">
          保存修改
        </button>
      </div>

      {/* Rewrite dialog overlay */}
      {showRewriteDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0"
            style={{ backgroundColor: 'oklch(0.10 0.02 260 / 0.8)' }}
            onClick={() => {
              if (rewritePhase === 'instruction') setShowRewriteDialog(null);
            }}
          />

          {/* === Instruction Phase === */}
          {rewritePhase === 'instruction' && (
            <div
              className="relative panel w-96 z-10"
              style={{ backgroundColor: 'var(--color-surface)' }}
            >
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-foreground)' }}>
                AI改写指令
              </h3>
              <textarea
                className="textarea-field text-sm mb-3"
                rows={3}
                placeholder="描述你想要的改写方向..."
                value={rewriteInstruction}
                onChange={(e) => setRewriteInstruction(e.target.value)}
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleRewrite(showRewriteDialog)}
                  className="btn-accent text-sm"
                >
                  执行改写
                </button>
                <button
                  onClick={() => setShowRewriteDialog(null)}
                  className="btn-ghost text-sm"
                >
                  取消
                </button>
              </div>
            </div>
          )}

          {/* === Loading Phase === */}
          {rewritePhase === 'loading' && (
            <div
              className="relative panel w-96 z-10 flex flex-col items-center justify-center py-8"
              style={{ backgroundColor: 'var(--color-surface)' }}
            >
              {/* Animated progress bar */}
              <div
                className="w-full mb-4 rounded overflow-hidden"
                style={{ backgroundColor: 'var(--color-base)', height: '4px' }}
              >
                <div
                  className="h-full rounded animate-pulse"
                  style={{
                    backgroundColor: 'var(--color-accent)',
                    width: '60%',
                    transition: 'width 0.3s ease-in-out',
                  }}
                />
              </div>

              {/* Spinner */}
              <Loader2
                size={24}
                className="animate-spin mb-3"
                style={{ color: 'var(--color-accent)' }}
              />

              {/* Loading text */}
              <p className="text-sm font-medium" style={{ color: 'var(--color-foreground)' }}>
                AI正在改写...
              </p>
              <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
                请稍候，改写结果即将呈现
              </p>
            </div>
          )}

          {/* === Diff Phase === */}
          {rewritePhase === 'diff' && (
            <div
              className="relative panel z-10"
              style={{ backgroundColor: 'var(--color-surface)', maxWidth: '520px', width: '520px' }}
            >
              {/* Header with accept/reject buttons */}
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold" style={{ color: 'var(--color-foreground)' }}>
                  改写对比
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRejectRewrite}
                    className="btn-ghost text-xs flex items-center gap-1"
                    style={{ color: 'var(--color-warning)' }}
                  >
                    <X size={12} />
                    拒绝
                  </button>
                  <button
                    onClick={handleAcceptRewrite}
                    className="btn-accent text-xs flex items-center gap-1"
                  >
                    采纳
                  </button>
                </div>
              </div>

              {/* Side-by-side before/after */}
              <div className="grid grid-cols-2 gap-2 mb-3">
                {/* Before (original) */}
                <div>
                  <div
                    className="text-xs font-semibold p-2 rounded-t"
                    style={{ backgroundColor: 'oklch(0.65 0.18 25 / 0.08)', color: 'var(--color-warning)' }}
                  >
                    原版
                  </div>
                  <div
                    className="p-2 rounded-b font-mono text-xs overflow-auto"
                    style={{ backgroundColor: 'var(--color-base)', maxHeight: '160px' }}
                  >
                    {rewriteOriginalContent.split('\n').map((line, i) => (
                      <div key={i} style={{ color: 'var(--color-foreground)' }}>
                        {line || '\u00A0'}
                      </div>
                    ))}
                  </div>
                </div>

                {/* After (rewritten) */}
                <div>
                  <div
                    className="text-xs font-semibold p-2 rounded-t"
                    style={{ backgroundColor: 'oklch(0.65 0.15 150 / 0.08)', color: 'var(--color-teal)' }}
                  >
                    改写版
                  </div>
                  <div
                    className="p-2 rounded-b font-mono text-xs overflow-auto"
                    style={{ backgroundColor: 'var(--color-base)', maxHeight: '160px' }}
                  >
                    {rewriteNewContent.split('\n').map((line, i) => (
                      <div key={i} style={{ color: 'var(--color-foreground)' }}>
                        {line || '\u00A0'}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Inline diff with color highlighting */}
              <div>
                <h4 className="text-xs font-semibold mb-1" style={{ color: 'var(--color-muted)' }}>
                  详细差异
                </h4>
                <div
                  className="font-mono text-xs space-y-0.5 overflow-auto p-2 rounded"
                  style={{ maxHeight: '160px', backgroundColor: 'var(--color-base)' }}
                >
                  {rewriteDiffLines.map((change, i) => (
                    <DiffLineView key={i} change={change} />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* === Diff Line View for inline coloring === */
function DiffLineView({ change }: { change: DiffLine }) {
  if (change.type === 'add') {
    return (
      <div
        className="flex items-center gap-1 py-0.5 px-2"
        style={{
          backgroundColor: 'oklch(0.65 0.15 150 / 0.1)',
          color: 'var(--color-teal)',
        }}
      >
        <Plus size={10} />
        <span className="flex-1">{change.content}</span>
      </div>
    );
  }
  if (change.type === 'remove') {
    return (
      <div
        className="flex items-center gap-1 py-0.5 px-2"
        style={{
          backgroundColor: 'oklch(0.65 0.18 25 / 0.1)',
          color: 'var(--color-warning)',
        }}
      >
        <Minus size={10} />
        <span className="flex-1">{change.content}</span>
      </div>
    );
  }
  return (
    <div
      className="flex items-center gap-1 py-0.5 px-2"
      style={{ color: 'var(--color-muted)' }}
    >
      <span className="flex-1">{change.content}</span>
    </div>
  );
}

interface ElementEditorProps {
  element: Element;
  isExpanded: boolean;
  isRewriting: boolean;
  onToggle: () => void;
  onRewrite: () => void;
  onSourceRefClick: (ref: SourceRef) => void;
}

function ElementEditor({
  element,
  isExpanded,
  isRewriting,
  onToggle,
  onRewrite,
  onSourceRefClick,
}: ElementEditorProps) {
  const typeLabel = getElementTypeLabel(element.type);
  const typeMarker = getElementTypeMarker(element.type);

  const typeColorMap: Record<ElementType, string> = {
    action: 'var(--color-foreground)',
    dialogue: 'var(--color-teal)',
    parenthetical: 'var(--color-muted)',
    transition: 'var(--color-accent)',
    voice_over: 'var(--color-accent-dim)',
    shot: 'var(--color-muted)',
    note: 'var(--color-muted)',
  };

  return (
    <div
      className="rounded p-2 cursor-pointer transition-colors"
      style={{ backgroundColor: 'var(--color-base)' }}
      onClick={onToggle}
    >
      {/* Collapsed view */}
      <div className="flex items-center gap-2">
        {isExpanded ? (
          <ChevronDown size={12} style={{ color: 'var(--color-muted)' }} />
        ) : (
          <ChevronRight size={12} style={{ color: 'var(--color-muted)' }} />
        )}
        <span
          className="badge shrink-0"
          style={{
            backgroundColor: 'var(--color-surface)',
            color: typeColorMap[element.type],
          }}
        >
          {typeLabel}
        </span>
        {element.character_id && (
          <span className="badge badge-teal shrink-0">
            {element.character_id}
          </span>
        )}
        <span
          className="text-xs truncate flex-1"
          style={{ color: typeColorMap[element.type] }}
        >
          {typeMarker && <span className="mr-1">{typeMarker}</span>}
          {element.content}
        </span>
        {/* Rewrite button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRewrite();
          }}
          className="shrink-0 p-1 rounded hover:bg-surfaceHover"
          style={{ color: 'var(--color-accent)' }}
        >
          {isRewriting ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <RefreshCw size={12} />
          )}
        </button>
      </div>

      {/* Expanded view */}
      {isExpanded && (
        <div className="mt-2 ml-4 space-y-2">
          <textarea
            className="textarea-field text-xs"
            rows={3}
            defaultValue={element.content}
          />
          {element.source_ref && (
            <button
              className="flex items-center gap-1 text-xs"
              style={{ color: 'var(--color-accent)' }}
              onClick={(e) => {
                e.stopPropagation();
                onSourceRefClick(element.source_ref!);
              }}
            >
              <Link size={10} />
              追踪来源: 段{element.source_ref.paragraph_index}
            </button>
          )}
          {element.note && (
            <div className="text-xs" style={{ color: 'var(--color-muted)' }}>
              备注: {element.note}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
