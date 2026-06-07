'use client';

import React from 'react';
import AppShell from '@/components/AppShell';
import ImportPage from '@/features/import/ImportPage';

export default function HomePage() {
  return (
    <AppShell>
      <ImportPage />
    </AppShell>
  );
}