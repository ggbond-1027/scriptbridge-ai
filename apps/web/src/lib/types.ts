/**
 * NovelScripter - TypeScript Type Definitions
 * Corresponding to backend Pydantic models
 */

/* === Element Types === */

export type ElementType =
  | 'action'
  | 'dialogue'
  | 'parenthetical'
  | 'transition'
  | 'voice_over'
  | 'shot'
  | 'note';

/* === Adaptation Styles === */

export type AdaptationStyle = 'short_series' | 'tv_series' | 'radio_drama' | 'stage_play';

export type DialogueStyle = 'natural' | 'restrained' | 'internet' | 'dramatic';

/* === Pipeline Stage === */

export type PipelineStage =
  | 'chapter_identification'
  | 'paragraph_numbering'
  | 'chapter_understanding'
  | 'story_bible_merge'
  | 'scene_splitting'
  | 'element_generation'
  | 'schema_validation';

export const PIPELINE_STAGES: PipelineStage[] = [
  'chapter_identification',
  'paragraph_numbering',
  'chapter_understanding',
  'story_bible_merge',
  'scene_splitting',
  'element_generation',
  'schema_validation',
];

export const PIPELINE_STAGE_LABELS: Record<PipelineStage, string> = {
  chapter_identification: '章节识别',
  paragraph_numbering: '段落编号',
  chapter_understanding: '逐章理解',
  story_bible_merge: '故事圣经合并',
  scene_splitting: '场景拆分',
  element_generation: '剧本元素生成',
  schema_validation: 'Schema校验',
};

/* === Source Reference === */

export interface SourceRef {
  chapter_id: string;
  paragraph_index: number;
  paragraph_ids?: string[];
  text_preview?: string;
}

/* === Scene Heading === */

export interface SceneHeading {
  context: string;
  location_id: string;
  time_of_day: string;
}

/* === Element === */

export interface Element {
  id: string;
  type: ElementType;
  content: string;
  character_id?: string;
  source_ref?: SourceRef;
  note?: string;
}

/* === Scene === */

export interface Scene {
  id: string;
  chapter_id: string;
  heading: SceneHeading;
  title: string;
  dramatic_purpose: string;
  conflict: string;
  beats: string[];
  elements: Element[];
  characters: string[];
  source_refs: SourceRef[];
  order_in_chapter: number;
  validation_errors?: string[];
}

/* === Chapter === */

export interface Chapter {
  id: string;
  title: string;
  number: number;
  start_marker?: string;
  end_marker?: string;
  paragraph_count: number;
  word_count: number;
  scenes: Scene[];
  preview_text?: string;
}

/* === Character === */

export interface Character {
  id: string; // char_XXX format
  name: string;
  aliases: string[];
  role: 'protagonist' | 'antagonist' | 'supporting' | 'minor' | 'narrator';
  description: string;
  goals: string[];
  personality: string;
  appearance: string;
  first_appearance: string;
  relationships: Relationship[];
}

export interface Relationship {
  target_id: string;
  type: string;
  description: string;
}

/* === Location === */

export interface Location {
  id: string; // loc_XXX format
  name: string;
  type: string;
  description: string;
  atmosphere: string;
  first_appearance: string;
}

/* === Timeline Entry === */

export interface TimelineEntry {
  id: string;
  event: string;
  chapter_id: string;
  scene_id?: string;
  characters: string[];
  timestamp_hint?: string;
  significance: string;
}

/* === Source Paragraph === */

export interface SourceParagraph {
  id: string;
  chapter_id: string;
  index: number;
  text: string;
  word_count: number;
  is_dialogue_hint?: boolean;
}

/* === Story Bible === */

export interface StoryBible {
  characters: Character[];
  locations: Location[];
  timeline: TimelineEntry[];
  themes?: string[];
  tone?: string;
  setting_description?: string;
}

/* === Generation Metadata === */

export interface GenerationMetadata {
  model_name: string;
  prompt_version: string;
  generation_time_ms: number;
  token_count?: number;
  cost_estimate?: number;
  timestamp: string;
}

/* === Screenplay === */

export interface Screenplay {
  id: string;
  title: string;
  adaptation_style: AdaptationStyle;
  dialogue_style: DialogueStyle;
  chapters: Chapter[];
  story_bible: StoryBible;
  metadata: GenerationMetadata;
  validation_errors: ValidationError[];
  created_at: string;
  updated_at: string;
}

/* === Validation Error === */

export interface ValidationError {
  id: string;
  type: 'missing_field' | 'invalid_reference' | 'duplicate' | 'format_error' | 'consistency';
  severity: 'error' | 'warning' | 'info';
  message: string;
  scene_id?: string;
  chapter_id?: string;
  character_id?: string;
  location_id?: string;
  field?: string;
  auto_fixable: boolean;
}

/* === Project Info === */

export interface ProjectInfo {
  id: string;
  name: string;
  source_text?: string;
  source_file?: string;
  screenplay: Screenplay;
  pipeline_status: PipelineStatus;
  created_at: string;
  updated_at: string;
}

/* === Pipeline Status === */

export interface PipelineStageStatus {
  stage: PipelineStage;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress: number;
  result_summary?: string;
  artifacts_count?: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface PipelineStatus {
  project_id: string;
  current_stage: PipelineStage;
  stages: PipelineStageStatus[];
  overall_progress: number;
  estimated_time_remaining?: number;
}

/* === API Request/Response Types === */

export interface CreateProjectRequest {
  name: string;
  source_text?: string;
  source_file?: File;
  adaptation_style: AdaptationStyle;
  dialogue_style: DialogueStyle;
}

export interface CreateProjectResponse {
  project_id: string;
  message: string;
}

export interface RepairRequest {
  error_ids?: string[];
  auto_fix?: boolean;
}

export interface RepairResponse {
  fixed_count: number;
  remaining_errors: ValidationError[];
  message: string;
}

export interface ExportRequest {
  format: 'yaml' | 'json' | 'markdown' | 'fountain' | 'zip' | 'docs';
  include_source_refs?: boolean;
  include_metadata?: boolean;
}

export interface ExportResponse {
  download_url: string;
  filename: string;
  format: string;
  size_bytes: number;
}

/* === Model Settings === */

export type ApiProvider = 'openai' | 'deepseek' | 'glm' | 'anthropic' | 'custom';

export type LocalEngine = 'ollama' | 'vllm' | 'llamacpp';

export interface ModelConfigPreset {
  provider: ApiProvider;
  label: string;
  defaultBaseUrl: string;
  defaultModel: string;
  keyPrefix: string;
}

export const API_PROVIDER_PRESETS: ModelConfigPreset[] = [
  { provider: 'openai',    label: 'OpenAI',          defaultBaseUrl: 'https://api.openai.com/v1',                  defaultModel: 'gpt-4o',            keyPrefix: 'sk-' },
  { provider: 'deepseek',  label: 'DeepSeek (深度求索)', defaultBaseUrl: 'https://api.deepseek.com/v1',               defaultModel: 'deepseek-chat',     keyPrefix: 'sk-' },
  { provider: 'glm',       label: 'GLM (智谱清言)',   defaultBaseUrl: 'https://open.bigmodel.cn/api/paas/v4',      defaultModel: 'glm-4-plus',        keyPrefix: '' },
  { provider: 'anthropic', label: 'Anthropic (Claude)', defaultBaseUrl: 'https://api.anthropic.com/v1',             defaultModel: 'claude-sonnet-4-20250514', keyPrefix: 'sk-ant-' },
  { provider: 'custom',    label: '自定义',           defaultBaseUrl: '',                                           defaultModel: '',                  keyPrefix: '' },
];

export const LOCAL_ENGINE_PRESETS: { engine: LocalEngine; label: string; defaultBaseUrl: string }[] = [
  { engine: 'ollama',   label: 'Ollama',    defaultBaseUrl: 'http://localhost:11434/v1' },
  { engine: 'vllm',     label: 'vLLM',      defaultBaseUrl: 'http://localhost:8000/v1' },
  { engine: 'llamacpp', label: 'llama.cpp', defaultBaseUrl: 'http://localhost:8080/v1' },
];

export interface ModelSettings {
  mode: 'api' | 'local';
  /* API mode */
  api_provider: ApiProvider;
  api_key: string;
  api_base_url: string;
  model_name: string;
  /* Local mode */
  local_engine: LocalEngine;
  local_base_url: string;
  local_model_name: string;
  /* Common params */
  temperature: number;
  max_tokens: number;
  /* Connection test result */
  connection_status: 'unknown' | 'testing' | 'connected' | 'failed';
  connection_error?: string;
}

/* === Diff Result === */

export interface DiffResult {
  element_id: string;
  before: string;
  after: string;
  changes: DiffLine[];
}

export interface DiffLine {
  type: 'add' | 'remove' | 'unchanged';
  content: string;
}

/* === Right Panel Tab === */

export type RightPanelTab = 'yaml' | 'preview' | 'docs' | 'logs';

/* === Sample Novel === */

export interface SampleNovel {
  id: string;
  title: string;
  author: string;
  description: string;
  text: string;
  chapters: number;
}
