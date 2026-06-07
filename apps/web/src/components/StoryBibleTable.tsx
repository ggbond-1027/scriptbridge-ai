'use client';

import React, { useMemo, useState } from 'react';
import {
  Users,
  MapPin,
  Clock,
  AlertTriangle,
  Merge,
  Edit2,
  Check,
  X,
  Search,
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  Target,
  Heart,
  BookOpen,
  Tag,
  GitBranch,
  ArrowRight,
  CornerDownLeft,
  CornerDownRight,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { storyBibleApi } from '@/lib/api';
import { Character, Location, TimelineEntry, Relationship } from '@/lib/types';
import CharacterCard from './CharacterCard';
import LocationCard from './LocationCard';
import RelationshipGraph from './RelationshipGraph';
import { showToast } from './Toast';

type BibleTab = 'characters' | 'locations' | 'timeline' | 'relationships';

export default function StoryBibleTable() {
  const {
    storyBible,
    project,
    updateCharacter,
    updateLocation,
    loadStoryBible,
    loadChapters,
    setSaveStatus,
  } = useProjectStore();
  const [activeTab, setActiveTab] = useState<BibleTab>('characters');
  const [editingCharacter, setEditingCharacter] = useState<string | null>(null);
  const [editingLocation, setEditingLocation] = useState<string | null>(null);
  const [showMergeDialog, setShowMergeDialog] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [ignoredMergePairs, setIgnoredMergePairs] = useState<Set<string>>(new Set());
  const duplicateSuggestions = useMemo(
    () => findDuplicateCharacters(storyBible?.characters ?? [])
      .filter((suggestion) => !ignoredMergePairs.has(getDuplicateSuggestionKey(suggestion))),
    [ignoredMergePairs, storyBible]
  );

  if (!storyBible) {
    return (
      <div className="text-center py-8" style={{ color: 'var(--color-muted)' }}>
        <p className="text-sm">故事圣经尚未生成</p>
        <p className="text-xs mt-1">等待Pipeline完成"故事圣经合并"阶段</p>
      </div>
    );
  }

  const handleMergeCharacters = async (suggestion: DuplicateSuggestion, targetId: string) => {
    if (!project) return;
    const sourceId = targetId === suggestion.id1 ? suggestion.id2 : suggestion.id1;
    const targetName = targetId === suggestion.id1 ? suggestion.name1 : suggestion.name2;

    setSaveStatus('saving');
    try {
      await storyBibleApi.mergeCharacters(project.id, [sourceId], targetId);
      await Promise.all([
        loadStoryBible(project.id),
        loadChapters(project.id),
      ]);
      setIgnoredMergePairs((prev) => {
        const next = new Set(prev);
        next.delete(getDuplicateSuggestionKey(suggestion));
        return next;
      });
      setSaveStatus('saved');
      showToast.success(`已合并为 ${targetName}`);
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch (error) {
      setSaveStatus('error');
      showToast.error(error instanceof Error ? error.message : '合并角色失败');
      throw error;
    }
  };

  const handleIgnoreMerge = (suggestion: DuplicateSuggestion) => {
    setIgnoredMergePairs((prev) => {
      const next = new Set(prev);
      next.add(getDuplicateSuggestionKey(suggestion));
      return next;
    });
    showToast.info('已忽略这条合并建议');
  };

  // Filter by search
  const filteredCharacters = storyBible.characters.filter((char) =>
    !searchQuery ||
    char.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    char.aliases.some((alias) => alias.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const filteredLocations = storyBible.locations.filter((loc) =>
    !searchQuery ||
    loc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    loc.type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredTimeline = storyBible.timeline.filter((entry) =>
    !searchQuery ||
    entry.event.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--color-muted)' }} />
          <input
            type="text"
            className="input-field text-sm pl-8"
            placeholder="搜索人物、地点或事件..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        {duplicateSuggestions.length > 0 && (
          <button
            onClick={() => setShowMergeDialog(true)}
            className="btn-ghost text-xs flex items-center gap-1"
            style={{ borderColor: 'var(--color-warning)' }}
          >
            <Merge size={12} />
            合并建议 ({duplicateSuggestions.length})
          </button>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b" style={{ borderColor: 'var(--color-border)' }}>
        <button
          className={`tab-item flex items-center gap-1 ${activeTab === 'characters' ? 'active' : ''}`}
          onClick={() => setActiveTab('characters')}
        >
          <Users size={14} />
          人物 ({storyBible.characters.length})
        </button>
        <button
          className={`tab-item flex items-center gap-1 ${activeTab === 'locations' ? 'active' : ''}`}
          onClick={() => setActiveTab('locations')}
        >
          <MapPin size={14} />
          地点 ({storyBible.locations.length})
        </button>
        <button
          className={`tab-item flex items-center gap-1 ${activeTab === 'timeline' ? 'active' : ''}`}
          onClick={() => setActiveTab('timeline')}
        >
          <Clock size={14} />
          时间线 ({storyBible.timeline.length})
        </button>
        <button
          className={`tab-item flex items-center gap-1 ${activeTab === 'relationships' ? 'active' : ''}`}
          onClick={() => setActiveTab('relationships')}
        >
          <GitBranch size={14} />
          关系图谱
        </button>
      </div>

      {/* Tab content */}
      {activeTab === 'characters' && (
        <CharactersTab
          characters={filteredCharacters}
          editingId={editingCharacter}
          onEdit={(id) => setEditingCharacter(id)}
          onSave={async (id, data) => {
            if (project) {
              await updateCharacter(project.id, id, data);
              setEditingCharacter(null);
            }
          }}
          onCancel={() => setEditingCharacter(null)}
        />
      )}

      {activeTab === 'locations' && (
        <LocationsTab
          locations={filteredLocations}
          editingId={editingLocation}
          onEdit={(id) => setEditingLocation(id)}
          onSave={async (id, data) => {
            if (project) {
              await updateLocation(project.id, id, data);
              setEditingLocation(null);
            }
          }}
          onCancel={() => setEditingLocation(null)}
        />
      )}

      {activeTab === 'timeline' && (
        <TimelineTab entries={filteredTimeline} />
      )}

      {activeTab === 'relationships' && (
        <div>
          <RelationshipGraph
            characters={storyBible.characters}
            timeline={storyBible.timeline}
            projectId={project?.id}
          />
          <p className="text-xs mt-2" style={{ color: 'var(--color-muted)' }}>
            人物关系图谱 - 显示角色之间的关联关系
          </p>
        </div>
      )}

      {/* Merge dialog */}
      {showMergeDialog && (
        <MergeDialog
          suggestions={duplicateSuggestions}
          onMerge={handleMergeCharacters}
          onIgnore={handleIgnoreMerge}
          onClose={() => setShowMergeDialog(false)}
        />
      )}
    </div>
  );
}

interface CharactersTabProps {
  characters: Character[];
  editingId: string | null;
  onEdit: (id: string) => void;
  onSave: (id: string, data: Partial<Character>) => Promise<void>;
  onCancel: () => void;
}

function CharactersTab({ characters, editingId, onEdit, onSave, onCancel }: CharactersTabProps) {
  const [editData, setEditData] = useState<Partial<Character>>({});

  const startEdit = (char: Character) => {
    setEditData({
      name: char.name,
      aliases: char.aliases,
      role: char.role,
      description: char.description,
      goals: char.goals,
      personality: char.personality,
      appearance: char.appearance,
      first_appearance: char.first_appearance,
      relationships: char.relationships,
    });
    onEdit(char.id);
  };

  const handleSave = async (id: string) => {
    await onSave(id, editData);
  };

  // Sort: protagonist and antagonist first
  const sorted = [...characters].sort((a, b) => {
    const order = { protagonist: 0, antagonist: 1, supporting: 2, narrator: 3, minor: 4 };
    return (order[a.role] || 5) - (order[b.role] || 5);
  });

  return (
    <div className="space-y-3">
      {sorted.map((char) => (
        editingId === char.id ? (
          <EditCharacterForm
            key={char.id}
            character={char}
            editData={editData}
            onChange={setEditData}
            onSave={() => handleSave(char.id)}
            onCancel={onCancel}
          />
        ) : (
          <CharacterCard
            key={char.id}
            character={char}
            isCore={char.role === 'protagonist' || char.role === 'antagonist'}
            onEdit={() => startEdit(char)}
          />
        )
      ))}
    </div>
  );
}

interface EditCharacterFormProps {
  character: Character;
  editData: Partial<Character>;
  onChange: (data: Partial<Character>) => void;
  onSave: () => void;
  onCancel: () => void;
}

function EditCharacterForm({ character, editData, onChange, onSave, onCancel }: EditCharacterFormProps) {
  const [syncWarning, setSyncWarning] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [addingRelationship, setAddingRelationship] = useState(false);
  const [newRel, setNewRel] = useState<Relationship>({ target_id: '', type: '', description: '' });

  const roleOptions: { value: Character['role']; label: string }[] = [
    { value: 'protagonist', label: '主角 (protagonist)' },
    { value: 'antagonist', label: '反派 (antagonist)' },
    { value: 'supporting', label: '配角 (supporting)' },
    { value: 'minor', label: '次要 (minor)' },
    { value: 'narrator', label: '叙述者 (narrator)' },
  ];

  const handleNameChange = (newName: string) => {
    onChange({ ...editData, name: newName });
    if (newName !== character.name) {
      setSyncWarning(true);
    } else {
      setSyncWarning(false);
    }
  };

  // Helper: aliases as comma-separated string
  const aliasesStr = (editData.aliases || []).join(', ');
  const handleAliasesChange = (val: string) => {
    const arr = val.split(',').map(s => s.trim()).filter(s => s.length > 0);
    onChange({ ...editData, aliases: arr });
  };

  // Helper: goals as newline-separated string
  const goalsStr = (editData.goals || []).join('\n');
  const handleGoalsChange = (val: string) => {
    const arr = val.split('\n').map(s => s.trim()).filter(s => s.length > 0);
    onChange({ ...editData, goals: arr });
  };

  // Helper: relationships
  const relationships = editData.relationships || [];

  const handleAddRelationship = () => {
    if (newRel.target_id.trim() && newRel.type.trim()) {
      onChange({ ...editData, relationships: [...relationships, { ...newRel }] });
      setNewRel({ target_id: '', type: '', description: '' });
      setAddingRelationship(false);
    }
  };

  const handleRemoveRelationship = (index: number) => {
    const updated = relationships.filter((_, i) => i !== index);
    onChange({ ...editData, relationships: updated });
  };

  return (
    <div className="panel" style={{ borderColor: 'var(--color-accent)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold" style={{ color: 'var(--color-accent)' }}>
          <Edit2 size={14} className="inline mr-1" />
          编辑角色: {character.name}
        </h4>
        <div className="flex items-center gap-1">
          <button onClick={onSave} className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-teal)' }}>
            <Check size={12} /> 保存
          </button>
          <button onClick={onCancel} className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-muted)' }}>
            <X size={12} /> 取消
          </button>
        </div>
      </div>

      {/* Sync warning */}
      {syncWarning && (
        <div className="mb-3 p-2 rounded text-xs" style={{ backgroundColor: 'oklch(0.75 0.15 75 / 0.1)', color: 'var(--color-accent)' }}>
          <AlertTriangle size={12} className="inline mr-1" />
          修改角色名称后，是否同步更新所有引用此角色的场景和对话？
        </div>
      )}

      {/* === Main Fields === */}
      <div className="space-y-3">
        {/* Name & Role - side by side */}
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="text-xs block mb-1" style={{ color: 'var(--color-muted)' }}>
              名称
            </label>
            <input
              type="text"
              className="input-field text-sm"
              value={editData.name || ''}
              onChange={(e) => handleNameChange(e.target.value)}
            />
          </div>
          <div className="w-[200px]">
            <label className="text-xs block mb-1" style={{ color: 'var(--color-muted)' }}>
              角色
            </label>
            <select
              className="input-field text-sm"
              value={editData.role || character.role}
              onChange={(e) => onChange({ ...editData, role: e.target.value as Character['role'] })}
            >
              {roleOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Aliases */}
        <div>
          <label className="text-xs flex items-center gap-1 mb-1" style={{ color: 'var(--color-muted)' }}>
            <Tag size={10} /> 别名
          </label>
          <input
            type="text"
            className="input-field text-sm"
            placeholder="多个别名用逗号分隔，如: 老李, 李叔"
            value={aliasesStr}
            onChange={(e) => handleAliasesChange(e.target.value)}
          />
          {aliasesStr && (
            <div className="flex items-center gap-1 mt-1">
              {(editData.aliases || []).map(alias => (
                <span key={alias} className="badge badge-muted">{alias}</span>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
          {/* Description */}
          <div className="min-w-0">
            <label className="text-xs block mb-1" style={{ color: 'var(--color-muted)' }}>
              描述
            </label>
            <textarea
              className="textarea-field text-sm"
              rows={3}
              value={editData.description || ''}
              onChange={(e) => onChange({ ...editData, description: e.target.value })}
            />
          </div>

          {/* Goals */}
          <div className="min-w-0">
            <label className="text-xs flex items-center gap-1 mb-1" style={{ color: 'var(--color-muted)' }}>
              <Target size={10} /> 目标
            </label>
            <textarea
              className="textarea-field text-sm"
              rows={3}
              placeholder="每行一个目标"
              value={goalsStr}
              onChange={(e) => handleGoalsChange(e.target.value)}
            />
          </div>

          {/* Personality */}
          <div className="min-w-0">
            <label className="text-xs block mb-1" style={{ color: 'var(--color-muted)' }}>
              性格
            </label>
            <textarea
              className="textarea-field text-sm"
              rows={3}
              value={editData.personality || ''}
              onChange={(e) => onChange({ ...editData, personality: e.target.value })}
            />
          </div>
        </div>
      </div>

      {/* === Collapsible: 详细信息 === */}
      <div className="mt-3">
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="flex items-center gap-1 text-xs w-full py-1.5 border-t"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-muted)' }}
        >
          {showDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          详细信息
          <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
            (外貌、首次出场、关系)
          </span>
        </button>

        {showDetails && (
          <div className="space-y-3 pt-2">
            {/* Appearance */}
            <div>
              <label className="text-xs flex items-center gap-1 mb-1" style={{ color: 'var(--color-muted)' }}>
                外貌
              </label>
              <textarea
                className="textarea-field text-sm"
                rows={2}
                value={editData.appearance || ''}
                onChange={(e) => onChange({ ...editData, appearance: e.target.value })}
              />
            </div>

            {/* First Appearance */}
            <div>
              <label className="text-xs flex items-center gap-1 mb-1" style={{ color: 'var(--color-muted)' }}>
                <BookOpen size={10} /> 首次出场
              </label>
              <input
                type="text"
                className="input-field text-sm"
                value={editData.first_appearance || ''}
                onChange={(e) => onChange({ ...editData, first_appearance: e.target.value })}
              />
            </div>

            {/* Relationships */}
            <div>
              <label className="text-xs flex items-center gap-1 mb-1" style={{ color: 'var(--color-muted)' }}>
                <Heart size={10} /> 关系
              </label>

              {/* Existing relationships list */}
              {relationships.length > 0 && (
                <div className="space-y-1 mb-2">
                  {relationships.map((rel, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 p-1.5 rounded text-xs"
                      style={{ backgroundColor: 'oklch(0.95 0.02 260 / 0.5)' }}
                    >
                      <span className="badge badge-muted">{rel.type}</span>
                      <span style={{ color: 'var(--color-foreground)' }}>{rel.target_id}</span>
                      {rel.description && (
                        <span className="truncate" style={{ color: 'var(--color-muted)' }}>{rel.description}</span>
                      )}
                      <button
                        onClick={() => handleRemoveRelationship(index)}
                        className="shrink-0"
                        style={{ color: 'var(--color-warning)' }}
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Add new relationship */}
              {!addingRelationship && (
                <button
                  onClick={() => setAddingRelationship(true)}
                  className="btn-ghost text-xs flex items-center gap-1"
                >
                  <Plus size={10} /> 添加关系
                </button>
              )}

              {addingRelationship && (
                <div className="p-2 rounded space-y-2" style={{ backgroundColor: 'oklch(0.95 0.02 260 / 0.3)' }}>
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <label className="text-xs block mb-0.5" style={{ color: 'var(--color-muted)' }}>目标角色ID</label>
                      <input
                        type="text"
                        className="input-field text-xs"
                        placeholder="如: char_001"
                        value={newRel.target_id}
                        onChange={(e) => setNewRel({ ...newRel, target_id: e.target.value })}
                      />
                    </div>
                    <div className="w-[120px]">
                      <label className="text-xs block mb-0.5" style={{ color: 'var(--color-muted)' }}>关系类型</label>
                      <input
                        type="text"
                        className="input-field text-xs"
                        placeholder="如: 朋友"
                        value={newRel.type}
                        onChange={(e) => setNewRel({ ...newRel, type: e.target.value })}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs block mb-0.5" style={{ color: 'var(--color-muted)' }}>描述</label>
                    <input
                      type="text"
                      className="input-field text-xs"
                      placeholder="关系描述"
                      value={newRel.description}
                      onChange={(e) => setNewRel({ ...newRel, description: e.target.value })}
                    />
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={handleAddRelationship}
                      className="btn-accent text-xs flex items-center gap-1"
                      disabled={!newRel.target_id.trim() || !newRel.type.trim()}
                    >
                      <Check size={10} /> 确认
                    </button>
                    <button
                      onClick={() => {
                        setAddingRelationship(false);
                        setNewRel({ target_id: '', type: '', description: '' });
                      }}
                      className="btn-ghost text-xs flex items-center gap-1"
                    >
                      <X size={10} /> 取消
                    </button>
                  </div>
                </div>
              )}

              {relationships.length === 0 && !addingRelationship && (
                <p className="text-xs" style={{ color: 'var(--color-muted)' }}>暂无关系记录</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface LocationsTabProps {
  locations: Location[];
  editingId: string | null;
  onEdit: (id: string) => void;
  onSave: (id: string, data: Partial<Location>) => Promise<void>;
  onCancel: () => void;
}

function LocationsTab({ locations, editingId, onEdit, onSave, onCancel }: LocationsTabProps) {
  return (
    <div className="space-y-3">
      {locations.map((loc) => (
        <LocationCard
          key={loc.id}
          location={loc}
          onEdit={() => onEdit(loc.id)}
        />
      ))}
    </div>
  );
}

interface TimelineTabProps {
  entries: TimelineEntry[];
}

function TimelineTab({ entries }: TimelineTabProps) {
  const rowSize = 3;
  const rows = [];
  for (let index = 0; index < entries.length; index += rowSize) {
    rows.push(entries.slice(index, index + rowSize));
  }

  return (
    <div className="space-y-4">
      <div className="hidden lg:block">
        <div className="space-y-8">
          {rows.map((row, rowIndex) => {
            const isReversed = rowIndex % 2 === 1;
            const orderedRow = isReversed ? [...row].reverse() : row;
            const rowStartIndex = rowIndex * rowSize;

            return (
              <div key={rowIndex} className="relative">
                <div className="grid grid-cols-3 gap-4">
                  {orderedRow.map((entry) => {
                    const sourceIndex = entries.findIndex((item) => item.id === entry.id);
                    return (
                      <TimelineEventCard
                        key={entry.id}
                        entry={entry}
                        index={sourceIndex}
                      />
                    );
                  })}
                </div>

                {orderedRow.length > 1 && (
                  <div className="pointer-events-none absolute inset-x-0 top-1/2 hidden grid-cols-3 gap-4 lg:grid">
                    {orderedRow.map((entry, visualIndex) => {
                      const isLast = visualIndex === orderedRow.length - 1;
                      if (isLast) return <span key={entry.id} />;
                      return (
                        <div
                          key={entry.id}
                          className={`flex ${isReversed ? 'justify-start' : 'justify-end'}`}
                          style={{ color: 'var(--color-accent)' }}
                        >
                          <ArrowRight
                            size={18}
                            className={isReversed ? 'rotate-180' : ''}
                          />
                        </div>
                      );
                    })}
                  </div>
                )}

                {rowIndex < rows.length - 1 && (
                  <div
                    className={`mt-3 flex items-center gap-2 text-xs ${
                      isReversed ? 'justify-start' : 'justify-end'
                    }`}
                    style={{ color: 'var(--color-accent)' }}
                  >
                    {isReversed ? <CornerDownLeft size={18} /> : <CornerDownRight size={18} />}
                    <span>继续到第 {Math.min(rowStartIndex + rowSize + 1, entries.length)} 步</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-3 lg:hidden">
        {entries.map((entry, index) => (
          <TimelineEventCard key={entry.id} entry={entry} index={index} compact />
        ))}
      </div>

      {entries.length === 0 && (
        <p className="text-center text-sm py-4" style={{ color: 'var(--color-muted)' }}>
          暂无时间线条目
        </p>
      )}
    </div>
  );
}

function TimelineEventCard({
  entry,
  index,
  compact = false,
}: {
  entry: TimelineEntry;
  index: number;
  compact?: boolean;
}) {
  return (
    <div
      className={`panel relative min-h-[132px] ${compact ? 'flex items-start gap-3' : ''}`}
      style={{ borderColor: index === 0 ? 'var(--color-accent)' : 'var(--color-border)' }}
    >
      <div className={`${compact ? 'shrink-0' : 'mb-2'} flex items-center gap-2`}>
        <span
          className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold"
          style={{
            backgroundColor: 'oklch(0.75 0.15 75 / 0.16)',
            color: 'var(--color-accent)',
            border: '1px solid oklch(0.75 0.15 75 / 0.35)',
          }}
        >
          {index + 1}
        </span>
        {!compact && <Clock size={13} style={{ color: 'var(--color-accent)' }} />}
      </div>
      <div className="min-w-0">
        <p className="text-sm leading-6" style={{ color: 'var(--color-foreground)' }}>
          {entry.event}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs" style={{ color: 'var(--color-muted)' }}>
          <span>章节: {entry.chapter_id}</span>
          {entry.scene_id && <span>场景: {entry.scene_id}</span>}
          <span>重要性: {entry.significance}</span>
        </div>
        {entry.characters.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1">
            {entry.characters.map((charId) => (
              <span key={charId} className="badge badge-teal">{charId}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface MergeDialogProps {
  suggestions: DuplicateSuggestion[];
  onMerge: (suggestion: DuplicateSuggestion, targetId: string) => Promise<void>;
  onIgnore: (suggestion: DuplicateSuggestion) => void;
  onClose: () => void;
}

function MergeDialog({ suggestions, onMerge, onIgnore, onClose }: MergeDialogProps) {
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const handleMerge = async (suggestion: DuplicateSuggestion, targetId: string) => {
    const key = `${getDuplicateSuggestionKey(suggestion)}:${targetId}`;
    setBusyKey(key);
    try {
      await onMerge(suggestion, targetId);
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ backgroundColor: 'oklch(0.10 0.02 260 / 0.8)' }}
        onClick={onClose}
      />
      <div
        className="relative panel z-10 max-h-[80vh] w-[calc(100vw-24px)] max-w-[520px] overflow-auto"
        style={{ backgroundColor: 'var(--color-surface)' }}
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold" style={{ color: 'var(--color-warning)' }}>
            <Merge size={14} className="inline mr-1" />
            合并建议 - 检测到可能重复的人物
          </h3>
          <button onClick={onClose} style={{ color: 'var(--color-muted)' }}>
            <X size={16} />
          </button>
        </div>

        <div className="space-y-3">
          {suggestions.map((suggestion, index) => (
            <div key={getDuplicateSuggestionKey(suggestion)} className="panel" style={{ borderColor: 'var(--color-warning)' }}>
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={14} style={{ color: 'var(--color-warning)' }} />
                <span className="text-sm" style={{ color: 'var(--color-foreground)' }}>
                  "{suggestion.name1}" 与 "{suggestion.name2}" 可能重复
                </span>
              </div>
              <p className="text-xs mb-2" style={{ color: 'var(--color-muted)' }}>
                原因: {suggestion.reason}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  className="btn-accent text-xs"
                  disabled={busyKey !== null}
                  onClick={() => handleMerge(suggestion, suggestion.id1)}
                >
                  {busyKey === `${getDuplicateSuggestionKey(suggestion)}:${suggestion.id1}` ? '合并中...' : `合并为 ${suggestion.name1}`}
                </button>
                <button
                  className="btn-ghost text-xs"
                  disabled={busyKey !== null}
                  onClick={() => handleMerge(suggestion, suggestion.id2)}
                >
                  {busyKey === `${getDuplicateSuggestionKey(suggestion)}:${suggestion.id2}` ? '合并中...' : `合并为 ${suggestion.name2}`}
                </button>
                <button
                  className="btn-ghost text-xs"
                  disabled={busyKey !== null}
                  style={{ borderColor: 'var(--color-muted)' }}
                  onClick={() => {
                    onIgnore(suggestion);
                    if (suggestions.length === 1) {
                      onClose();
                    }
                  }}
                >
                  不合并
                </button>
              </div>
            </div>
          ))}
          {suggestions.length === 0 && (
            <p className="text-center text-sm py-4" style={{ color: 'var(--color-muted)' }}>
              暂无待处理的合并建议
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

interface DuplicateSuggestion {
  id1: string;
  name1: string;
  id2: string;
  name2: string;
  reason: string;
}

function findDuplicateCharacters(characters: Character[]): DuplicateSuggestion[] {
  const suggestions: DuplicateSuggestion[] = [];

  for (let i = 0; i < characters.length; i++) {
    for (let j = i + 1; j < characters.length; j++) {
      const a = characters[i];
      const b = characters[j];

      // Check for similar names
      if (a.name.toLowerCase() === b.name.toLowerCase()) {
        suggestions.push({
          id1: a.id,
          name1: a.name,
          id2: b.id,
          name2: b.name,
          reason: '名称完全相同',
        });
      }
      // Check for name appearing in aliases
      else if (a.aliases.some((alias) => alias.toLowerCase() === b.name.toLowerCase())) {
        suggestions.push({
          id1: a.id,
          name1: a.name,
          id2: b.id,
          name2: b.name,
          reason: `"${b.name}" 是 "${a.name}" 的别名`,
        });
      }
      else if (b.aliases.some((alias) => alias.toLowerCase() === a.name.toLowerCase())) {
        suggestions.push({
          id1: b.id,
          name1: b.name,
          id2: a.id,
          name2: a.name,
          reason: `"${a.name}" 是 "${b.name}" 的别名`,
        });
      }
      // Check for overlapping aliases
      else {
        const overlap = a.aliases.filter(
          (alias) => b.aliases.some((bAlias) => alias.toLowerCase() === bAlias.toLowerCase())
        );
        if (overlap.length > 0) {
          suggestions.push({
            id1: a.id,
            name1: a.name,
            id2: b.id,
            name2: b.name,
            reason: `共享别名: ${overlap.join(', ')}`,
          });
        }
      }
    }
  }

  return suggestions;
}

function getDuplicateSuggestionKey(suggestion: DuplicateSuggestion): string {
  return [suggestion.id1, suggestion.id2].sort().join('__');
}
