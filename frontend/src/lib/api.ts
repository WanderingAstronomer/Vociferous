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

export interface Transcript {
    id: number;
    timestamp: string;
    raw_text: string;
    normalized_text: string;
    text: string;
    display_name: string | null;
    duration_ms: number;
    speech_duration_ms: number;
    transcription_time_ms: number;
    refinement_time_ms: number;
    created_at: string;
    include_in_analytics: boolean;
    has_audio_cached: boolean;
    is_protected: boolean;
    tags: Tag[];
}

export interface Tag {
    id: number;
    name: string;
    color: string | null;
    is_system: boolean;
}

export interface PaginatedResult<T> {
    items: T[];
    total: number;
}

export interface TranscriptListParams {
    limit?: number;
    offset?: number;
    sort_by?: string;
    sort_dir?: "asc" | "desc";
    tag_ids?: number[];
    tag_mode?: "any" | "all";
}

export function getTranscripts(params: TranscriptListParams = {}): Promise<PaginatedResult<Transcript>> {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    if (params.sort_by) q.set("sort_by", params.sort_by);
    if (params.sort_dir) q.set("sort_dir", params.sort_dir);
    if (params.tag_ids?.length) q.set("tag_ids", params.tag_ids.join(","));
    if (params.tag_mode) q.set("tag_mode", params.tag_mode);
    const qs = q.toString();
    return request(`/transcripts${qs ? `?${qs}` : ""}`);
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

export interface SearchResult {
    items: Transcript[];
    total: number;
    offset: number;
    limit: number;
}

export function searchTranscripts(q: string, limit = 50, offset = 0): Promise<SearchResult> {
    return request(`/transcripts/search?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`);
}

export function refineTranscript(id: number, level: number, instructions = ""): Promise<{ status: string }> {
    return request(`/transcripts/${id}/refine`, {
        method: "POST",
        body: JSON.stringify({ level, instructions }),
    });
}

export function commitRefinement(id: number, text: string): Promise<{ status: string }> {
    return request(`/transcripts/${id}/refine/commit`, {
        method: "POST",
        body: JSON.stringify({ text }),
    });
}

export function bulkRefineTranscripts(
    ids: number[],
    level: number,
    instructions = "",
    skipRefined = true,
): Promise<{ status: string; total: number }> {
    return request("/transcripts/batch-refine", {
        method: "POST",
        body: JSON.stringify({ ids, level, instructions, skip_refined: skipRefined }),
    });
}

export function cancelBulkRefinement(): Promise<{ status: string }> {
    return request("/transcripts/batch-refine/cancel", { method: "POST" });
}

export function renameTranscript(id: number, title: string): Promise<{ status: string; title: string }> {
    return request(`/transcripts/${id}/rename`, {
        method: "POST",
        body: JSON.stringify({ title }),
    });
}

export function retranscribeTranscript(id: number): Promise<{ status: string }> {
    return request(`/transcripts/${id}/retranscribe`, { method: "POST" });
}

// --- Tags ---

export function getTags(): Promise<Tag[]> {
    return request("/tags");
}

export function createTag(name: string, color?: string): Promise<{ status: string }> {
    return request("/tags", {
        method: "POST",
        body: JSON.stringify({ name, color: color ?? null }),
    });
}

export function updateTag(id: number, updates: { name?: string; color?: string }): Promise<{ status: string }> {
    return request(`/tags/${id}`, {
        method: "PUT",
        body: JSON.stringify(updates),
    });
}

export function deleteTag(id: number): Promise<{ deleted: boolean }> {
    return request(`/tags/${id}`, { method: "DELETE" });
}

export function assignTags(transcriptId: number, tagIds: number[]): Promise<{ status: string }> {
    return request(`/transcripts/${transcriptId}/tags`, {
        method: "POST",
        body: JSON.stringify({ tag_ids: tagIds }),
    });
}

/**
 * Add or remove a single tag from multiple transcripts in one server round-trip.
 * add=true → insert the tag on all transcripts that lack it (preserves other tags).
 * add=false → remove the tag from all specified transcripts (preserves other tags).
 */
export function batchToggleTag(
    transcriptIds: number[],
    tagId: number,
    add: boolean,
): Promise<{ toggled: number }> {
    return request("/transcripts/batch-tag-toggle", {
        method: "POST",
        body: JSON.stringify({ transcript_ids: transcriptIds, tag_id: tagId, add }),
    });
}

/**
 * Batch-delete multiple transcripts in a single server round-trip.
 */
export async function batchDeleteTranscripts(
    transcriptIds: number[],
): Promise<{ deleted: number }> {
    if (transcriptIds.length === 0) return { deleted: 0 };
    return request("/transcripts/batch-delete", {
        method: "POST",
        body: JSON.stringify({ ids: transcriptIds }),
    });
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
    model_file: string;
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

export interface GpuInfo {
    cuda_available: boolean;
    driver_detected: boolean;
    cuda_device_count: number;
    gpu_name: string;
    detail: string;
    slm_gpu_layers: number;
    vram_total_mb: number;
    vram_used_mb: number;
    vram_free_mb: number;
}

export interface MicInfo {
    available: boolean;
    device_name: string;
    host_api: string;
    input_channels: number;
    default_sample_rate: number;
    supports_16k: boolean;
    detail: string;
}

export interface HealthInfo {
    status: string;
    version: string;
    transcripts: number;
    recording_active?: boolean;
    gpu?: GpuInfo;
    mic?: MicInfo;
}

export function getHealth(): Promise<HealthInfo> {
    return request("/health");
}

export function getInsight(): Promise<{ text: string }> {
    return request("/insight");
}

export function exportFile(content: string, filename: string): Promise<{ path: string }> {
    return request("/export", {
        method: "POST",
        body: JSON.stringify({ content, filename }),
    });
}

export async function importAudioFile(file: File): Promise<{ status: string; file: string; dispatched: boolean }> {
    const form = new FormData();
    form.append("data", file, file.name);
    const res = await fetch(`${BASE}/import-audio`, { method: "POST", body: form });
    if (!res.ok) {
        const body = await res.text();
        throw new Error(`API ${res.status}: ${body}`);
    }
    return res.json();
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
