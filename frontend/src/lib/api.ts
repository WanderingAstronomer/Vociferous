/**
 * Vociferous API client — thin wrapper around fetch for the Litestar REST API.
 */

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
        headers: { "Content-Type": "application/json", ...options?.headers },
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
    kind: string;
    text: string;
    model_id: string | null;
    created_at: string;
}

export interface Transcript {
    id: number;
    timestamp: string;
    raw_text: string;
    normalized_text: string;
    text: string;
    display_name: string | null;
    duration_ms: number;
    speech_duration_ms: number;
    project_id: number | null;
    project_name: string | null;
    current_variant_id: number | null;
    created_at: string;
    variants?: TranscriptVariant[];
}

export interface Project {
    id: number;
    name: string;
    color: string | null;
    parent_id: number | null;
}

export function getTranscripts(limit = 50, projectId?: number): Promise<Transcript[]> {
    let url = `/transcripts?limit=${limit}`;
    if (projectId != null) url += `&project_id=${projectId}`;
    return request(url);
}

export function getTranscript(id: number): Promise<Transcript> {
    return request(`/transcripts/${id}`);
}

export function deleteTranscript(id: number): Promise<{ deleted: boolean }> {
    return request(`/transcripts/${id}`, { method: "DELETE" });
}

export function searchTranscripts(q: string, limit = 50): Promise<Transcript[]> {
    return request(`/transcripts/search?q=${encodeURIComponent(q)}&limit=${limit}`);
}

export function refineTranscript(id: number, level: number, instructions = ""): Promise<{ status: string }> {
    return request(`/transcripts/${id}/refine`, {
        method: "POST",
        body: JSON.stringify({ level, instructions }),
    });
}

// --- Projects ---

export function getProjects(): Promise<Project[]> {
    return request("/projects");
}

export function createProject(name: string, color?: string): Promise<Project> {
    return request("/projects", {
        method: "POST",
        body: JSON.stringify({ name, color }),
    });
}

export function deleteProject(id: number): Promise<{ deleted: boolean }> {
    return request(`/projects/${id}`, { method: "DELETE" });
}

// --- Config ---

export function getConfig(): Promise<Record<string, unknown>> {
    return request("/config");
}

export function updateConfig(updates: Record<string, unknown>): Promise<Record<string, unknown>> {
    return request("/config", {
        method: "PUT",
        body: JSON.stringify(updates),
    });
}

// --- Models ---

export interface ModelInfo {
    name: string;
    filename: string;
    size_mb: number;
    repo_id: string;
}

export function getModels(): Promise<{ asr: Record<string, ModelInfo>; slm: Record<string, ModelInfo> }> {
    return request("/models");
}

// --- Health ---

export function getHealth(): Promise<{ status: string; version: string; transcripts: number }> {
    return request("/health");
}

// --- Intent dispatch ---

export function dispatchIntent(type: string, payload: Record<string, unknown> = {}): Promise<{ dispatched: boolean }> {
    return request("/intents", {
        method: "POST",
        body: JSON.stringify({ type, ...payload }),
    });
}
