/**
 * NovelScripter - YAML Utilities
 * Parse, serialize, validate, and format YAML data
 */

import yaml from 'js-yaml';

/**
 * Parse a YAML string into a JavaScript object
 */
export function parseYaml(content: string): unknown {
  try {
    return yaml.load(content);
  } catch (error) {
    if (error instanceof yaml.YAMLException) {
      throw new YamlError(error.message, error.mark?.line ?? 0, error.mark?.column ?? 0);
    }
    throw error;
  }
}

/**
 * Serialize a JavaScript object into a YAML string
 */
export function serializeYaml(data: unknown, options?: yaml.DumpOptions): string {
  return yaml.dump(data, {
    indent: 2,
    lineWidth: 120,
    noRefs: true,
    sortKeys: false,
    quotingType: '"',
    forceQuotes: false,
    ...options,
  });
}

/**
 * Validate YAML syntax and return errors
 */
export function validateYaml(content: string): YamlError[] {
  const errors: YamlError[] = [];
  try {
    yaml.load(content, {
      onWarning: (warning) => {
        if (warning instanceof yaml.YAMLException && warning.mark) {
          errors.push(
            new YamlError(
              warning.message,
              warning.mark.line,
              warning.mark.column,
              'warning'
            )
          );
        }
      },
    });
  } catch (error) {
    if (error instanceof yaml.YAMLException && error.mark) {
      errors.push(
        new YamlError(
          error.message,
          error.mark.line,
          error.mark.column,
          'error'
        )
      );
    }
  }
  return errors;
}

/**
 * Format YAML content (re-parse and re-serialize for consistent formatting)
 */
export function formatYaml(content: string): string {
  const parsed = parseYaml(content);
  return serializeYaml(parsed);
}

/**
 * Extract a specific section from YAML by path
 * e.g., getYamlSection(content, 'story_bible.characters')
 */
export function getYamlSection(content: string, path: string): unknown {
  const parsed = parseYaml(content) as Record<string, unknown>;
  const parts = path.split('.');
  let current: unknown = parsed;

  for (const part of parts) {
    if (current && typeof current === 'object' && part in (current as Record<string, unknown>)) {
      current = (current as Record<string, unknown>)[part];
    } else {
      return undefined;
    }
  }

  return current;
}

/**
 * Get line number for a YAML key
 */
export function getYamlKeyLine(content: string, keyPath: string): number | null {
  const lines = content.split('\n');
  const parts = keyPath.split('.');
  const lastKey = parts[parts.length - 1];
  const indentLevel = parts.length - 1;
  const expectedIndent = indentLevel * 2;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trimStart();
    const currentIndent = line.length - trimmed.length;

    if (currentIndent === expectedIndent && trimmed.startsWith(`${lastKey}:`)) {
      return i + 1; // 1-based line number
    }
  }

  return null;
}

/**
 * Highlight YAML errors by marking error lines
 */
export function highlightYamlErrors(
  content: string,
  errors: YamlError[]
): YamlLineInfo[] {
  const lines = content.split('\n');
  return lines.map((line, index) => {
    const lineNum = index + 1;
    const error = errors.find((e) => e.line === lineNum);
    return {
      lineNumber: lineNum,
      content: line,
      error: error || null,
    };
  });
}

/**
 * Custom YAML error class
 */
export class YamlError extends Error {
  constructor(
    message: string,
    public line: number,
    public column: number,
    public severity: 'error' | 'warning' = 'error'
  ) {
    super(message);
    this.name = 'YamlError';
  }
}

export interface YamlLineInfo {
  lineNumber: number;
  content: string;
  error: YamlError | null;
}

/**
 * Convert a Screenplay object to YAML
 */
export function screenplayToYaml(screenplay: unknown): string {
  return serializeYaml(screenplay, {
    styles: {
      '!!null': 'canonical', // dump null as ~
    },
  });
}

/**
 * Parse YAML back to Screenplay object
 */
export function yamlToScreenplay(content: string): unknown {
  return parseYaml(content);
}

/**
 * Generate a YAML schema snippet for documentation
 */
export function generateSchemaSnippet(): string {
  const schema = {
    screenplay: {
      title: 'string',
      adaptation_style: 'short_series | tv_series | radio_drama | stage_play',
      dialogue_style: 'natural | restrained | internet | dramatic',
      chapters: [
        {
          id: 'string (chap_XXX)',
          title: 'string',
          number: 'integer',
          scenes: [
            {
              id: 'string (sc_XXX)',
              heading: {
                context: 'INT. | EXT.',
                location_id: 'string (loc_XXX)',
                time_of_day: 'DAY | NIGHT | CONTINUOUS',
              },
              title: 'string',
              dramatic_purpose: 'string',
              conflict: 'string',
              beats: ['string'],
              elements: [
                {
                  id: 'string (elm_XXX)',
                  type: 'action | dialogue | parenthetical | transition | voice_over | shot | note',
                  content: 'string',
                  character_id: 'string (char_XXX)?',
                },
              ],
              characters: ['string (char_XXX)'],
              source_refs: [
                {
                  chapter_id: 'string',
                  paragraph_index: 'integer',
                },
              ],
            },
          ],
        },
      ],
      story_bible: {
        characters: [
          {
            id: 'string (char_XXX)',
            name: 'string',
            aliases: ['string'],
            role: 'protagonist | antagonist | supporting | minor | narrator',
            goals: ['string'],
            personality: 'string',
            relationships: [
              {
                target_id: 'string (char_XXX)',
                type: 'string',
                description: 'string',
              },
            ],
          },
        ],
        locations: [
          {
            id: 'string (loc_XXX)',
            name: 'string',
            type: 'string',
            atmosphere: 'string',
          },
        ],
      },
    },
  };

  return serializeYaml(schema);
}