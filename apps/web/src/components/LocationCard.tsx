'use client';

import React from 'react';
import { MapPin, Cloud, Building, Trees, Home, Landmark } from 'lucide-react';
import { Location } from '@/lib/types';

interface LocationCardProps {
  location: Location;
  onEdit?: () => void;
  onSelect?: () => void;
}

const locationTypeIcons: Record<string, React.ReactNode> = {
  indoor: <Building size={14} />,
  outdoor: <Trees size={14} />,
  urban: <Home size={14} />,
  landmark: <Landmark size={14} />,
  nature: <Cloud size={14} />,
};

export default function LocationCard({ location, onEdit, onSelect }: LocationCardProps) {
  const typeIcon = locationTypeIcons[location.type] || <MapPin size={14} />;

  return (
    <div
      className="panel cursor-pointer transition-all"
      style={{ borderLeft: '3px solid var(--color-teal)' }}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--color-teal)' }}>{typeIcon}</span>
          <span className="font-semibold text-sm" style={{ color: 'var(--color-foreground)' }}>
            {location.name}
          </span>
          <span className="badge badge-teal">{location.type}</span>
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

      {/* Description */}
      {location.description && (
        <p className="text-xs mb-2" style={{ color: 'var(--color-muted)' }}>
          {location.description.slice(0, 100)}
          {location.description.length > 100 ? '...' : ''}
        </p>
      )}

      {/* Atmosphere */}
      {location.atmosphere && (
        <div className="text-xs mb-1" style={{ color: 'var(--color-muted)' }}>
          <span className="font-medium" style={{ color: 'var(--color-teal)' }}>氛围: </span>
          {location.atmosphere}
        </div>
      )}

      {/* First appearance */}
      {location.first_appearance && (
        <div className="text-xs" style={{ color: 'var(--color-muted)' }}>
          首次出现: {location.first_appearance}
        </div>
      )}
    </div>
  );
}