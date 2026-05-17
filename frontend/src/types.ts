export type Role = "user" | "admin";

export interface SessionUser {
  id: string;
  username: string;
  role: Role;
}

export interface VoiceStatus {
  status: string;
  adapter: string;
  message: string;
  sample_filename?: string | null;
  sample_filenames?: string[];
  sample_count?: number;
  error?: string | null;
  model_id?: string | null;
  job_id?: string | null;
}

export interface CloneStyle {
  catchphrases: string[];
  particles: string[];
  punctuation: string[];
  emoji_style: string[];
  message_format: string[];
  typing_habits: string[];
  address_terms: string[];
  example_dialogues: string[];
  average_length: number;
}

export interface CloneMemory {
  keyTopics: string[];
  key_topics: string[];
  summary: string;
  relationship_overview: string[];
  timeline: string[];
  daily_patterns: string[];
  shared_experiences: string[];
  inside_jokes: string[];
  food_preferences: string[];
  interests: string[];
  conflict_patterns: string[];
  sweet_moments: string[];
  breakup_notes: string[];
}

export interface CloneProfile {
  cloneId: string;
  name: string;
  style: CloneStyle;
  memory: CloneMemory;
  rules: Record<string, string[]>;
  corrections: string[];
  sourceStats: Record<string, unknown>;
  voice: VoiceStatus | null;
}

export interface ChatReply {
  clone_id: string;
  text: string;
  emotion: string;
}

export interface SpeechResult {
  status: string;
  backend: string;
  message: string;
  audioDataUrl: string | null;
  contentType: string | null;
  emotion: string;
}

export interface AdminResource {
  userId?: string;
  username?: string;
  cloneId?: string;
  cloneName?: string;
  vectorDbName?: string;
  chunkCount: number;
  vectorDbSizeBytes: number;
  voiceModelStatus: string;
  voiceModelSizeBytes: number;
}

export interface AdminSummary {
  vectorDbCount: number;
  totalVectorDbSizeBytes: number;
  totalVoiceModelSizeBytes: number;
  resources: AdminResource[];
}

export interface UploadedFile {
  name: string;
  data: string;
}
