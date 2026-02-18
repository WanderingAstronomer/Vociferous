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

export function clearAllTranscripts(): Promise<{ deleted: number }> {
    return request("/transcripts", { method: "DELETE" });
}

export function deleteVariant(transcriptId: number, variantId: number): Promise<{ deleted: boolean }> {
    return request(`/transcripts/${transcriptId}/variants/${variantId}`, { method: "DELETE" });
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

export function createProject(name: string, color?: string, parentId?: number | null): Promise<Project> {
    return request("/projects", {
        method: "POST",
        body: JSON.stringify({ name, color, parent_id: parentId ?? null }),
    });
}

export function updateProject(
    id: number,
    updates: { name?: string; color?: string; parent_id?: number | null },
): Promise<{ status: string }> {
    return request(`/projects/${id}`, {
        method: "PUT",
        body: JSON.stringify(updates),
    });
}

export function deleteProject(id: number): Promise<{ deleted: boolean }> {
    return request(`/projects/${id}`, { method: "DELETE" });
}

export function assignProject(transcriptId: number, projectId: number | null): Promise<{ dispatched: boolean }> {
    return dispatchIntent("assign_project", { transcript_id: transcriptId, project_id: projectId });
}

/**
 * Batch-assign multiple transcripts to a project.
 * Fires individual intents for each — no backend batch endpoint needed.
 */
export async function batchAssignProject(
    transcriptIds: number[],
    projectId: number | null,
): Promise<{ succeeded: number; failed: number }> {
    let succeeded = 0;
    let failed = 0;
    for (const id of transcriptIds) {
        try {
            await assignProject(id, projectId);
            succeeded++;
        } catch {
            failed++;
        }
    }
    return { succeeded, failed };
}

/**
 * Batch-delete multiple transcripts.
 */
export async function batchDeleteTranscripts(
    transcriptIds: number[],
): Promise<{ succeeded: number; failed: number }> {
    let succeeded = 0;
    let failed = 0;
    for (const id of transcriptIds) {
        try {
            await deleteTranscript(id);
            succeeded++;
        } catch {
            failed++;
        }
    }
    return { succeeded, failed };
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
    id: string;
    name: string;
    filename: string;
    repo: string;
    size_mb: number;
    tier: string;
    downloaded: boolean;
    quant?: string;
}

export function getModels(): Promise<{ asr: Record<string, ModelInfo>; slm: Record<string, ModelInfo> }> {
    return request("/models");
}

// --- Health ---

export function getHealth(): Promise<{ status: string; version: string; transcripts: number; recording_active?: boolean }> {
    return request("/health");
}

export function getInsight(): Promise<{ text: string }> {
    return request("/insight");
}

export function getMotd(): Promise<{ text: string }> {
    return request("/motd");
}

export function exportFile(content: string, filename: string): Promise<{ path: string }> {
    return request("/export", {
        method: "POST",
        body: JSON.stringify({ content, filename }),
    });
}

export function restartEngine(): Promise<{ status: string }> {
    return request("/engine/restart", { method: "POST" });
}

export function downloadModel(modelType: "asr" | "slm", modelId: string): Promise<{ status: string; model_id: string }> {
    return request("/models/download", {
        method: "POST",
        body: JSON.stringify({ model_type: modelType, model_id: modelId }),
    });
}

// --- Intent dispatch ---

export function dispatchIntent(type: string, payload: Record<string, unknown> = {}): Promise<{ dispatched: boolean }> {
    return request("/intents", {
        method: "POST",
        body: JSON.stringify({ type, ...payload }),
    });
}

// --- Key Capture ---

export function startKeyCapture(): Promise<{ status: string }> {
    return request("/keycapture/start", { method: "POST" });
}

export function stopKeyCapture(): Promise<{ status: string }> {
    return request("/keycapture/stop", { method: "POST" });
}

// --- Window control ---

export function minimizeWindow(): Promise<{ status: string }> {
    return request("/window/minimize", { method: "POST" });
}

export function maximizeWindow(): Promise<{ status: string; maximized?: boolean }> {
    return request("/window/maximize", { method: "POST" });
}

export function closeWindow(): Promise<{ status: string }> {
    return request("/window/close", { method: "POST" });
}
