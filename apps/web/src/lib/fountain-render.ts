/**
 * NovelScripter - Fountain Format Renderer
 * Converts screenplay data to Fountain markup and renders it as HTML
 */

import { Scene, Element, ElementType } from './types';

/**
 * Fountain format constants
 */
const FOUNTAIN_SCENE_HEADING_PREFIXES = ['INT.', 'EXT.', 'INT./EXT.', 'EXT./INT.', 'I/E.'];

/**
 * Convert a Scene object to Fountain markup string
 * @param scene The Scene to convert
 * @param locationNames Optional map of location_id -> location name for resolving headings
 */
export function sceneToFountain(scene: Scene, locationNames?: Record<string, string>): string {
  const lines: string[] = [];

  // Scene heading
  const heading = formatSceneHeading(scene, locationNames);
  lines.push(heading);

  // Scene title (as a comment)
  if (scene.title) {
    lines.push(`[[${scene.title}]]`);
  }

  // Dramatic purpose (as a comment)
  if (scene.dramatic_purpose) {
    lines.push(`/* Dramatic purpose: ${scene.dramatic_purpose} */`);
  }

  // Conflict (as a comment)
  if (scene.conflict) {
    lines.push(`/* Conflict: ${scene.conflict} */`);
  }

  // Beats (as comments) — ensure beats is an array (LLM may return string)
  const beats = Array.isArray(scene.beats) ? scene.beats : (typeof scene.beats === 'string' && scene.beats ? [scene.beats] : []);
  if (beats.length > 0) {
    lines.push(`/* Beats: ${beats.join(', ')} */`);
  }

  lines.push('');

  // Elements
  for (const element of scene.elements) {
    const fountainLine = elementToFountain(element);
    lines.push(fountainLine);
  }

  return lines.join('\n');
}

/**
 * Convert an Element to Fountain markup
 */
export function elementToFountain(element: Element): string {
  switch (element.type) {
    case 'action':
      return element.content;

    case 'dialogue':
      if (element.character_id) {
        return `${element.character_id.toUpperCase()}\n${element.content}`;
      }
      return element.content;

    case 'parenthetical':
      return `(${element.content})`;

    case 'transition':
      return `> ${element.content.toUpperCase()}.`;

    case 'voice_over':
      if (element.character_id) {
        return `${element.character_id.toUpperCase()} (V.O.)\n${element.content}`;
      }
      return `${element.content} (V.O.)`;

    case 'shot':
      return element.content.toUpperCase();

    case 'note':
      return `/* ${element.content} */`;

    default:
      return element.content;
  }
}

/**
 * Format a SceneHeading into a Fountain scene heading
 * @param scene The Scene whose heading to format
 * @param locationNames Optional map of location_id -> location name for resolving headings
 */
export function formatSceneHeading(scene: Scene, locationNames?: Record<string, string>): string {
  const { heading } = scene;
  const context = heading.context.toUpperCase();
  const locationId = heading.location_id;
  const timeOfDay = heading.time_of_day.toUpperCase();

  // Resolve location_id to name using the provided map, or fall back to raw id
  const locationName = (locationNames && locationNames[locationId]) || locationId;
  return `${context} ${locationName} - ${timeOfDay}`;
}

/**
 * Convert multiple scenes to a complete Fountain document
 * @param scenes Array of Scene objects to convert
 * @param title Optional screenplay title for the title page
 * @param locationNames Optional map of location_id -> location name for resolving headings
 */
export function screenplayToFountain(scenes: Scene[], title?: string, locationNames?: Record<string, string>): string {
  const parts: string[] = [];

  // Title page
  if (title) {
    parts.push(`Title: ${title}`);
    parts.push('Credit: NovelScripter AI');
    parts.push('Author: --');
    parts.push('Draft date: --');
    parts.push('');
    parts.push('');
  }

  // Scenes
  for (const scene of scenes) {
    parts.push(sceneToFountain(scene, locationNames));
    parts.push('');
  }

  return parts.join('\n');
}

/**
 * Render Fountain markup to HTML
 */
export function renderFountainToHtml(fountainText: string): string {
  const lines = fountainText.split('\n');
  const htmlLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      htmlLines.push('<br/>');
      continue;
    }

    // Title page elements (lines before first scene heading in the first block)
    if (trimmed.startsWith('Title:')) {
      htmlLines.push(`<h1 class="script-title">${escapeHtml(trimmed.slice(7))}</h1>`);
      continue;
    }
    if (trimmed.startsWith('Credit:')) {
      htmlLines.push(`<p class="script-credit">${escapeHtml(trimmed.slice(8))}</p>`);
      continue;
    }
    if (trimmed.startsWith('Author:')) {
      htmlLines.push(`<p class="script-author">${escapeHtml(trimmed.slice(8))}</p>`);
      continue;
    }

    // Scene heading: INT. or EXT. prefix
    if (isSceneHeading(trimmed)) {
      htmlLines.push(`<div class="script-scene-heading">${escapeHtml(trimmed)}</div>`);
      continue;
    }

    // Transition: > TO SOMETHING.
    if (trimmed.startsWith('>')) {
      htmlLines.push(`<div class="script-transition">${escapeHtml(trimmed)}</div>`);
      continue;
    }

    // Shot: centered uppercase with specific patterns
    if (/^(CLOSE UP|WIDE|POV|ANGLE|INSERT|FLASHBACK|FADE)/i.test(trimmed)) {
      htmlLines.push(`<div class="script-shot">${escapeHtml(trimmed)}</div>`);
      continue;
    }

    // Note: /* ... */
    if (trimmed.startsWith('/*') && trimmed.endsWith('*/')) {
      htmlLines.push(`<div class="script-note">${escapeHtml(trimmed)}</div>`);
      continue;
    }

    // Boneyard: /* ... */ (multi-line, skip for now)

    // Parenthetical: starts with (
    if (trimmed.startsWith('(')) {
      htmlLines.push(`<div class="script-parenthetical">${escapeHtml(trimmed)}</div>`);
      continue;
    }

    // Character name: all uppercase, possibly with (V.O.) or (O.S.)
    if (/^[A-Z][A-Z\s\.]+$/.test(trimmed) || /^[A-Z][A-Z\s\.]+\s*\((V\.O\.|O\.S\.|CONT'D)\)$/i.test(trimmed)) {
      htmlLines.push(`<div class="script-character">${escapeHtml(trimmed)}</div>`);
      continue;
    }

    // Dialogue: follows a character name
    // We detect this contextually — if previous line was a character name, this is dialogue
    if (i > 0 && isCharacterLine(lines[i - 1]?.trim())) {
      htmlLines.push(`<div class="script-dialogue">${escapeHtml(trimmed)}</div>`);
      continue;
    }

    // Section heading: # Section
    if (trimmed.startsWith('#')) {
      const level = trimmed.match(/^#+/)?.[0]?.length || 1;
      const content = trimmed.replace(/^#+\s*/, '');
      htmlLines.push(`<h${Math.min(level + 1, 6)} class="script-section">${escapeHtml(content)}</h${Math.min(level + 1, 6)}>`);
      continue;
    }

    // Synopsis: = Synopsis text
    if (trimmed.startsWith('=')) {
      htmlLines.push(`<div class="script-synopsis">${escapeHtml(trimmed.slice(2))}</div>`);
      continue;
    }

    // Action / default: anything else
    htmlLines.push(`<div class="script-action">${escapeHtml(trimmed)}</div>`);
  }

  return htmlLines.join('\n');
}

/**
 * Check if a line is a Fountain scene heading
 */
function isSceneHeading(line: string): boolean {
  return FOUNTAIN_SCENE_HEADING_PREFIXES.some((prefix) =>
    line.toUpperCase().startsWith(prefix)
  );
}

/**
 * Check if a line is a character name in Fountain
 */
function isCharacterLine(line: string): boolean {
  if (!line) return false;
  const trimmed = line.trim();
  return /^[A-Z][A-Z\s\.]+$/.test(trimmed) || /^[A-Z][A-Z\s\.]+\s*\((V\.O\.|O\.S\.|CONT'D)\)$/i.test(trimmed);
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (char) => map[char] || char);
}

/**
 * Get element type display name in Chinese
 */
export function getElementTypeLabel(type: ElementType): string {
  const labels: Record<ElementType, string> = {
    action: '动作',
    dialogue: '对话',
    parenthetical: '括注',
    transition: '转场',
    voice_over: '旁白',
    shot: '镜头',
    note: '备注',
  };
  return labels[type] || type;
}

/**
 * Get element type Fountain marker
 */
export function getElementTypeMarker(type: ElementType): string {
  const markers: Record<ElementType, string> = {
    action: '',
    dialogue: '',
    parenthetical: '()',
    transition: '>',
    voice_over: '(V.O.)',
    shot: '',
    note: '/* */',
  };
  return markers[type];
}