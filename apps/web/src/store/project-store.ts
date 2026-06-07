/**
 * NovelScripter - Project Store (Zustand)
 * Manages project state, screenplay data, and CRUD operations
 */

import { create } from 'zustand';
import {
  ProjectInfo,
  Screenplay,
  StoryBible,
  Chapter,
  Scene,
  SourceParagraph,
  ValidationError,
  AdaptationStyle,
  DialogueStyle,
  RightPanelTab,
} from '@/lib/types';
import { projectApi, screenplayApi, chapterApi, sceneApi, sourceApi, validationApi, storyBibleApi } from '@/lib/api';

/** 确保值为数组 — LLM可能返回字符串而不是数组 */
function ensureList(value: unknown): any[] {
  if (Array.isArray(value)) return value;
  if (typeof value === 'string' && value.trim()) return [value];
  if (value === null || value === undefined) return [];
  return [value];
}

/** 对后端返回的原始数据做类型清洗 — 将LLM可能返回为字符串的数组字段统一转为数组 */
function normalizeChapters(chapters: any[]): Chapter[] {
  return chapters.map((ch) => ({
    ...ch,
    scenes: (Array.isArray(ch.scenes) ? ch.scenes : []).map(normalizeScene),
  }));
}

function normalizeScene(scene: any): Scene {
  return {
    ...scene,
    characters: ensureList(scene.characters),
    beats: ensureList(scene.beats),
    elements: Array.isArray(scene.elements) ? scene.elements : [],
    source_refs: Array.isArray(scene.source_refs) ? scene.source_refs : [],
    validation_errors: ensureList(scene.validation_errors),
  };
}

function normalizeStoryBible(sb: any): StoryBible {
  return {
    ...sb,
    characters: (Array.isArray(sb.characters) ? sb.characters : []).map(normalizeCharacter),
    locations: Array.isArray(sb.locations) ? sb.locations : [],
    timeline: (Array.isArray(sb.timeline) ? sb.timeline : []).map((entry: any) => ({
      ...entry,
      characters: ensureList(entry.characters),
    })),
    themes: ensureList(sb.themes),
  };
}

function normalizeCharacter(char: any): any {
  return {
    ...char,
    aliases: ensureList(char.aliases),
    goals: ensureList(char.goals),
    relationships: ensureList(char.relationships),
  };
}

interface ProjectState {
  /* === Core data === */
  project: ProjectInfo | null;
  screenplay: Screenplay | null;
  chapters: Chapter[];
  storyBible: StoryBible | null;
  validationErrors: ValidationError[];

  /* === Selection state === */
  selectedChapterId: string | null;
  selectedSceneId: string | null;
  selectedParagraphIndex: number | null;
  highlightedSourceRefs: string[];

  /* === UI state === */
  rightPanelTab: RightPanelTab;
  rightPanelCollapsed: boolean;
  leftPanelWidth: number;
  rightPanelWidth: number;
  isLoading: boolean;
  error: string | null;
  saveStatus: 'idle' | 'saving' | 'saved' | 'error';

  /* === Source paragraphs cache === */
  paragraphsCache: Record<string, SourceParagraph[]>;

  /* === Actions === */
  loadProject: (projectId: string) => Promise<void>;
  loadChapters: (projectId: string) => Promise<void>;
  loadStoryBible: (projectId: string) => Promise<void>;
  loadValidationErrors: (projectId: string) => Promise<void>;
  loadParagraphs: (projectId: string, chapterId: string) => Promise<void>;

  selectChapter: (chapterId: string) => void;
  selectScene: (sceneId: string) => void;
  selectParagraph: (index: number) => void;
  highlightSourceRefs: (refs: string[]) => void;
  clearHighlight: () => void;

  setRightPanelTab: (tab: RightPanelTab) => void;
  toggleRightPanel: () => void;
  setLeftPanelWidth: (width: number) => void;
  setRightPanelWidth: (width: number) => void;
  setSaveStatus: (status: 'idle' | 'saving' | 'saved' | 'error') => void;

  /* === Mutation actions === */
  updateScene: (projectId: string, sceneId: string, data: Partial<Scene>) => Promise<void>;
  updateCharacter: (projectId: string, characterId: string, data: Partial<unknown>) => Promise<void>;
  updateLocation: (projectId: string, locationId: string, data: Partial<unknown>) => Promise<void>;
  rewriteElement: (projectId: string, sceneId: string, elementId: string, instruction?: string) => Promise<void>;
  repairErrors: (projectId: string, errorIds?: string[]) => Promise<void>;

  reset: () => void;
}

const initialState = {
  project: null,
  screenplay: null,
  chapters: [],
  storyBible: null,
  validationErrors: [],
  selectedChapterId: null,
  selectedSceneId: null,
  selectedParagraphIndex: null,
  highlightedSourceRefs: [],
  rightPanelTab: 'yaml' as RightPanelTab,
  rightPanelCollapsed: false,
  leftPanelWidth: 240,
  rightPanelWidth: 320,
  isLoading: false,
  error: null,
  saveStatus: 'idle' as 'idle' | 'saving' | 'saved' | 'error',
  paragraphsCache: {} as Record<string, SourceParagraph[]>,
};

export const useProjectStore = create<ProjectState>((set, get) => ({
  ...initialState,

  loadProject: async (projectId: string) => {
    set({ isLoading: true, error: null });
    try {
      const project = await projectApi.get(projectId);
      // Extract screenplay data from project response if available
      const screenplay = project.screenplay || null;
      set({ project, screenplay, isLoading: false });
      // Load related data
      get().loadChapters(projectId);
      get().loadStoryBible(projectId);
      get().loadValidationErrors(projectId);
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to load project',
      });
    }
  },

  loadChapters: async (projectId: string) => {
    try {
      const rawChapters = await chapterApi.list(projectId);
      const chapters = normalizeChapters(rawChapters);
      set({ chapters });
      // Auto-select first chapter if none selected
      if (!get().selectedChapterId && chapters.length > 0) {
        set({ selectedChapterId: chapters[0].id });
        get().loadParagraphs(projectId, chapters[0].id);
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load chapters',
      });
    }
  },

  loadStoryBible: async (projectId: string) => {
    try {
      const rawStoryBible = await storyBibleApi.get(projectId);
      const storyBible = normalizeStoryBible(rawStoryBible);
      set({ storyBible });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load story bible',
      });
    }
  },

  loadValidationErrors: async (projectId: string) => {
    try {
      const errors = await validationApi.getErrors(projectId);
      set({ validationErrors: errors });
    } catch (err) {
      // Validation errors are non-critical, don't set global error
      console.error('Failed to load validation errors:', err);
    }
  },

  loadParagraphs: async (projectId: string, chapterId: string) => {
    try {
      const paragraphs = await sourceApi.getParagraphs(projectId, chapterId);
      set({
        paragraphsCache: {
          ...get().paragraphsCache,
          [chapterId]: paragraphs,
        },
      });
    } catch (err) {
      console.error('Failed to load paragraphs:', err);
    }
  },

  selectChapter: (chapterId: string) => {
    set({ selectedChapterId: chapterId, selectedSceneId: null, selectedParagraphIndex: null });
    const { project } = get();
    if (project) {
      get().loadParagraphs(project.id, chapterId);
    }
  },

  selectScene: (sceneId: string) => {
    set({ selectedSceneId: sceneId });
  },

  selectParagraph: (index: number) => {
    set({ selectedParagraphIndex: index });
  },

  highlightSourceRefs: (refs: string[]) => {
    set({ highlightedSourceRefs: refs });
  },

  clearHighlight: () => {
    set({ highlightedSourceRefs: [] });
  },

  setRightPanelTab: (tab: RightPanelTab) => {
    set({ rightPanelTab: tab, rightPanelCollapsed: false });
  },

  toggleRightPanel: () => {
    set({ rightPanelCollapsed: !get().rightPanelCollapsed });
  },

  setLeftPanelWidth: (width: number) => {
    set({ leftPanelWidth: width });
  },

  setRightPanelWidth: (width: number) => {
    set({ rightPanelWidth: width });
  },

  setSaveStatus: (status) => {
    set({ saveStatus: status });
  },

  updateScene: async (projectId: string, sceneId: string, data: Partial<Scene>) => {
    set({ saveStatus: 'saving' });
    try {
      const updatedScene = await sceneApi.update(projectId, sceneId, data);
      // Update the scene in chapters
      const chapters = get().chapters.map((chapter) => ({
        ...chapter,
        scenes: chapter.scenes.map((scene) =>
          scene.id === sceneId ? updatedScene : scene
        ),
      }));
      set({ chapters, saveStatus: 'saved' });
      // Reset save status after a delay
      setTimeout(() => set({ saveStatus: 'idle' }), 3000);
    } catch (err) {
      set({
        saveStatus: 'error',
        error: err instanceof Error ? err.message : 'Failed to update scene',
      });
    }
  },

  updateCharacter: async (projectId: string, characterId: string, data: Partial<unknown>) => {
    set({ saveStatus: 'saving' });
    try {
      const updatedCharacter = await storyBibleApi.updateCharacter(
        projectId,
        characterId,
        data as Partial<import('@/lib/types').Character>
      );
      const { storyBible } = get();
      if (storyBible) {
        set({
          storyBible: {
            ...storyBible,
            characters: storyBible.characters.map((char) =>
              char.id === characterId ? updatedCharacter : char
            ),
          },
          saveStatus: 'saved',
        });
      }
      setTimeout(() => set({ saveStatus: 'idle' }), 3000);
    } catch (err) {
      set({
        saveStatus: 'error',
        error: err instanceof Error ? err.message : 'Failed to update character',
      });
    }
  },

  updateLocation: async (projectId: string, locationId: string, data: Partial<unknown>) => {
    set({ saveStatus: 'saving' });
    try {
      const updatedLocation = await storyBibleApi.updateLocation(
        projectId,
        locationId,
        data as Partial<import('@/lib/types').Location>
      );
      const { storyBible } = get();
      if (storyBible) {
        set({
          storyBible: {
            ...storyBible,
            locations: storyBible.locations.map((loc) =>
              loc.id === locationId ? updatedLocation : loc
            ),
          },
          saveStatus: 'saved',
        });
      }
      setTimeout(() => set({ saveStatus: 'idle' }), 3000);
    } catch (err) {
      set({
        saveStatus: 'error',
        error: err instanceof Error ? err.message : 'Failed to update location',
      });
    }
  },

  rewriteElement: async (projectId: string, sceneId: string, elementId: string, instruction?: string) => {
    try {
      const updatedElement = await sceneApi.rewriteElement(projectId, sceneId, elementId, instruction);
      // Update the element in chapters
      const chapters = get().chapters.map((chapter) => ({
        ...chapter,
        scenes: chapter.scenes.map((scene) =>
          scene.id === sceneId
            ? {
                ...scene,
                elements: scene.elements.map((el) =>
                  el.id === elementId ? updatedElement : el
                ),
              }
            : scene
        ),
      }));
      set({ chapters });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to rewrite element',
      });
    }
  },

  repairErrors: async (projectId: string, errorIds?: string[]) => {
    try {
      const result = await validationApi.repair(projectId, { error_ids: errorIds, auto_fix: true });
      // Refresh validation errors
      get().loadValidationErrors(projectId);
      // Refresh screenplay data since repair may have modified it
      get().loadChapters(projectId);
      get().loadStoryBible(projectId);
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to repair errors',
      });
    }
  },

  reset: () => {
    set(initialState);
  },
}));