'use client';

import React, { useEffect } from 'react';
import { Toaster as SonnerToaster, toast } from 'sonner';

export default function Toast() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        style: {
          backgroundColor: 'oklch(0.22 0.03 260)',
          color: 'oklch(0.90 0.01 260)',
          border: '1px solid oklch(0.35 0.03 260)',
        },
      }}
      theme="dark"
    />
  );
}

/**
 * Helper functions for showing toast notifications
 */
export const showToast = {
  success: (message: string) => {
    toast.success(message, {
      style: {
        backgroundColor: 'oklch(0.22 0.03 260)',
        color: 'oklch(0.90 0.01 260)',
        border: '1px solid oklch(0.35 0.03 260)',
      },
    });
  },

  error: (message: string) => {
    toast.error(message, {
      style: {
        backgroundColor: 'oklch(0.22 0.03 260)',
        color: 'oklch(0.90 0.01 260)',
        border: '1px solid oklch(0.65 0.18 25)',
      },
    });
  },

  warning: (message: string) => {
    toast.warning(message, {
      style: {
        backgroundColor: 'oklch(0.22 0.03 260)',
        color: 'oklch(0.90 0.01 260)',
        border: '1px solid oklch(0.75 0.15 75)',
      },
    });
  },

  info: (message: string) => {
    toast.info(message, {
      style: {
        backgroundColor: 'oklch(0.22 0.03 260)',
        color: 'oklch(0.90 0.01 260)',
        border: '1px solid oklch(0.55 0.12 150)',
      },
    });
  },

  promise: <T,>(promise: Promise<T>, messages: {
    loading: string;
    success: string | ((data: T) => string);
    error: string | ((error: unknown) => string);
  }) => {
    return toast.promise(promise, {
      loading: messages.loading,
      success: messages.success,
      error: messages.error,
      style: {
        backgroundColor: 'oklch(0.22 0.03 260)',
        color: 'oklch(0.90 0.01 260)',
        border: '1px solid oklch(0.35 0.03 260)',
      },
    });
  },
};