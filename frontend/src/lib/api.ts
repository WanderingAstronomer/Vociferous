/**
 * Vociferous API client — thin wrapper around fetch for the Litestar REST API.
 */

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// --- Transcripts ---

export interface TranscriptVariant {
  id: number;
  transcript_id: number;
  variant_type: string;
  content: string;
  is_current: boolean;
  created_at: string;
}

export interface Transcript {
  id: number;
  raw_text: string;
  language: string;
  model_id: string;
  duration_ms: number;
  project_id: number | null;
  created_at: string;
  variants: TranscriptVariant[];
}

export interface HistoryEntry {
  id: number;
  raw_text: string;
  display_text: string;
  language: string;
  model_id: string;
  duration_ms: number;
  project_id: number | null;
  created_at: string;
}

export interface Project {
  id: number;
  name: string;
  created_at: string;
}

export function getTranscripts(limit = 50, offset = 0): Promise<HistoryEntry[]> {
  return request(`/transcripts?limit=${limit}&offset=${offset}`);
}

export function getTranscript(id: number): Promise<Transcript> {
  return request(`/transcripts/${id}`);
}

export function deleteTranscript(id: number): Promise<void> {
  return request(`/transcripts/${id}`, { method: 'DELETE' });
}

export function searchTranscripts(q: string): Promise<HistoryEntry[]> {
  return request(`/search?q=${encodeURIComponent(q)}`);
}

export function refineTranscript(id: number, level: number): Promise<{ variant_id: number; content: string }> {
  return request(`/transcripts/${id}/refine`, {
    method: 'POST',
    body: JSON.stringify({ level }),
  });
}

// --- Projects ---

export function getProjects(): Promise<Project[]> {
  return request('/projects');
}

export function createProject(name: string): Promise<Project> {
  return request('/projects', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

export function deleteProject(id: number): Promise<void> {
  return request(`/projects/${id}`, { method: 'DELETE' });
}

// --- Config ---

export function getConfig(): Promise<Record<string, unknown>> {
  return request('/config');
}

export function updateConfig(updates: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request('/config', {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

// --- Models ---

export function getModels(): Promise<{ asr: Record<string, unknown>; slm: Record<string, unknown> }> {
  return request('/models');
}

// --- Health ---

export function getHealth(): Promise<{ status: string; version: string }> {
  return request('/health');
}

// --- Intents (generic dispatch) ---

export function dispatchIntent(intentType: string, payload: Record<string, unknown> = {}): Promise<{ ok: boolean }> {
  return request('/intents', {
    method: 'POST',
    body: JSON.stringify({ type: intentType, ...payload }),
  });
}
