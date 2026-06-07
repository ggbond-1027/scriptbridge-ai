'use client';

import React from 'react';
import {
  Star,
  Target,
  Heart,
  BookOpen,
  ArrowRight,
  Tag,
} from 'lucide-react';
import { Character } from '@/lib/types';

interface CharacterCardProps {
  character: Character;
  isCore?: boolean;
  onEdit?: () => void;
  onSelect?: () => void;
}

/** 确保值为数组 — LLM可能返回字符串而不是数组 */
function ensureList(value: unknown): string[] {
  if (Array.isArray(value)) return value;
  if (typeof value === 'string' && value.trim()) return [value];
  return [];
}

export default function CharacterCard({ character, isCore, onEdit, onSelect }: CharacterCardProps) {
  const roleLabels: Record<string, string> = {
    protagonist: '主角',
    antagonist: '反派',
    supporting: '配角',
    minor: '次要',
    narrator: '叙述者',
  };

  const roleBadgeClass = character.role === 'protagonist' || character.role === 'antagonist'
    ? 'badge-accent'
    : character.role === 'supporting'
      ? 'badge-teal'
      : 'badge-muted';

  // 安全地获取数组字段
  const goals = ensureList(character.goals);
  const aliases = ensureList(character.aliases);
  const relationships = ensureList(character.relationships);

  return (
    <div
      className="panel cursor-pointer transition-all"
      style={{
        borderLeft: `3px solid ${isCore ? 'var(--color-accent)' : 'var(--color-teal)'}`,
      }}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {isCore && <Star size={14} style={{ color: 'var(--color-accent)' }} />}
          <span className="font-semibold text-sm" style={{ color: 'var(--color-foreground)' }}>
            {character.name}
          </span>
          <span className={`badge ${roleBadgeClass}`}>
            {roleLabels[character.role] || character.role}
          </span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onEdit?.();
          }}
          className="text-xs"
          style={{ color: 'var(--color-accent)' }}
        >
          编辑
        </button>
      </div>

      {/* Aliases */}
      {aliases.length > 0 && (
        <div className="flex items-center gap-1 mb-2">
          <Tag size={10} style={{ color: 'var(--color-muted)' }} />
          {aliases.map((alias) => (
            <span key={alias} className="badge badge-muted">{alias}</span>
          ))}
        </div>
      )}

      {/* Description */}
      {character.description && (
        <p className="text-xs mb-2" style={{ color: 'var(--color-muted)' }}>
          {character.description.slice(0, 100)}
          {character.description.length > 100 ? '...' : ''}
        </p>
      )}

      {/* Goals */}
      {goals.length > 0 && (
        <div className="mb-2">
          <div className="flex items-center gap-1 text-xs mb-1" style={{ color: 'var(--color-accent-dim)' }}>
            <Target size={10} />
            <span>目标</span>
          </div>
          {goals.slice(0, 3).map((goal, i) => (
            <div key={i} className="text-xs ml-3" style={{ color: 'var(--color-muted)' }}>
              - {goal}
            </div>
          ))}
        </div>
      )}

      {/* Personality */}
      {character.personality && (
        <div className="mb-2 text-xs" style={{ color: 'var(--color-muted)' }}>
          <span className="font-medium" style={{ color: 'var(--color-accent-dim)' }}>性格: </span>
          {character.personality.slice(0, 80)}
        </div>
      )}

      {/* Appearance */}
      {character.appearance && (
        <div className="mb-2 text-xs" style={{ color: 'var(--color-muted)' }}>
          <span className="font-medium" style={{ color: 'var(--color-teal)' }}>外貌: </span>
          {character.appearance.slice(0, 80)}
        </div>
      )}

      {/* Relationships */}
      {relationships.length > 0 && (
        <div className="mt-2">
          <div className="flex items-center gap-1 text-xs mb-1" style={{ color: 'var(--color-teal)' }}>
            <Heart size={10} />
            <span>关系</span>
          </div>
          {relationships.slice(0, 3).map((rel: any, i: number) => (
            <div key={i} className="flex items-center gap-1 text-xs ml-3" style={{ color: 'var(--color-muted)' }}>
              <ArrowRight size={8} />
              <span className="badge badge-muted">{rel.type}</span>
              <span>{rel.target_id}</span>
              <span className="truncate">{rel.description}</span>
            </div>
          ))}
        </div>
      )}

      {/* First appearance */}
      {character.first_appearance && (
        <div className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
          <BookOpen size={10} className="inline mr-1" />
          首次出场: {character.first_appearance}
        </div>
      )}
    </div>
  );
}