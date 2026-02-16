/**
 * Typed WebSocket event definitions.
 *
 * Discriminated union of all server→client events, ensuring type-safe
 * handling throughout the frontend. Event shapes mirror the Python
 * `event_bus.emit()` calls in ApplicationCoordinator and API routes.
 */

// --- Individual event data types ---

export interface RecordingStartedData {
    // Empty payload — recording has begun
}

export interface RecordingStoppedData {
    cancelled: boolean;
}

export interface TranscriptionCompleteData {
    text: string;
    id: number | null;
    duration_ms: number;
    speech_duration_ms: number;
}

export interface TranscriptionErrorData {
    message: string;
}

export interface AudioLevelData {
    level: number;
}

export interface AudioSpectrumData {
    bands: number[];
}

export interface RefinementStartedData {
    transcript_id: number;
    level: number;
}

export interface RefinementCompleteData {
    transcript_id: number;
    text: string;
    level: number;
}

export interface RefinementErrorData {
    transcript_id?: number;
    message: string;
}

export interface TranscriptDeletedData {
    id: number;
}

export interface TranscriptUpdatedData {
    id: number;
    variant_id: number;
}

export interface ConfigUpdatedData {
    [key: string]: unknown;
}

export interface EngineStatusData {
    asr?: string;
    slm?: string;
}

export interface OnboardingRequiredData {
    reason: string;
}

export interface DownloadProgressData {
    model_id: string;
    status: "started" | "downloading" | "complete" | "error";
    message: string;
}

export interface ProjectCreatedData {
    id: number;
    name: string;
    color: string | null;
}

export interface ProjectDeletedData {
    id: number;
}

export interface KeyCapturedData {
    combo: string;
    display: string;
}

// --- Event type → data mapping ---

export interface WSEventMap {
    recording_started: RecordingStartedData;
    recording_stopped: RecordingStoppedData;
    transcription_complete: TranscriptionCompleteData;
    transcription_error: TranscriptionErrorData;
    audio_level: AudioLevelData;
    audio_spectrum: AudioSpectrumData;
    refinement_started: RefinementStartedData;
    refinement_complete: RefinementCompleteData;
    refinement_error: RefinementErrorData;
    transcript_deleted: TranscriptDeletedData;
    transcript_updated: TranscriptUpdatedData;
    config_updated: ConfigUpdatedData;
    engine_status: EngineStatusData;
    onboarding_required: OnboardingRequiredData;
    download_progress: DownloadProgressData;
    project_created: ProjectCreatedData;
    project_deleted: ProjectDeletedData;
    key_captured: KeyCapturedData;
}

/** All known event type strings. */
export type WSEventType = keyof WSEventMap;

/** Type-safe event handler for a specific event type. */
export type TypedEventHandler<T extends WSEventType> = (data: WSEventMap[T]) => void;
