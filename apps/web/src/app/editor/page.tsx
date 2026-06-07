'use client';

import React from 'react';
import AppShell from '@/components/AppShell';
import EditorPage from '@/features/editor/EditorPage';

export default function EditorRoute() {
  return (
    <AppShell>
      <EditorPage />
    </AppShell>
  );
}