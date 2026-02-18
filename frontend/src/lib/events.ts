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

export interface RefinementProgressData {
    transcript_id: number;
    message?: string;
    elapsed_seconds?: number;
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

export interface InsightReadyData {
    text: string;
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
    refinement_progress: RefinementProgressData;
    transcript_deleted: TranscriptDeletedData;
    transcript_updated: TranscriptUpdatedData;
    config_updated: ConfigUpdatedData;
    engine_status: EngineStatusData;
    onboarding_required: OnboardingRequiredData;
    download_progress: DownloadProgressData;
    project_created: ProjectCreatedData;
    project_deleted: ProjectDeletedData;
    key_captured: KeyCapturedData;
    insight_ready: InsightReadyData;
}

/** All known event type strings. */
export type WSEventType = keyof WSEventMap;

/** Type-safe event handler for a specific event type. */
export type TypedEventHandler<T extends WSEventType> = (data: WSEventMap[T]) => void;

export type EventValidator<T extends WSEventType> = (
    data: unknown,
) => data is WSEventMap[T];

const isObject = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

const isNumber = (value: unknown): value is number =>
    typeof value === "number" && Number.isFinite(value);

const isString = (value: unknown): value is string => typeof value === "string";

const isBoolean = (value: unknown): value is boolean => typeof value === "boolean";

const isNumberArray = (value: unknown): value is number[] =>
    Array.isArray(value) && value.every((item) => isNumber(item));

const isDownloadStatus = (
    value: unknown,
): value is DownloadProgressData["status"] =>
    value === "started" ||
    value === "downloading" ||
    value === "complete" ||
    value === "error";

export const wsEventValidators: {
    [K in WSEventType]: EventValidator<K>;
} = {
    recording_started: (data): data is RecordingStartedData => isObject(data),
    recording_stopped: (data): data is RecordingStoppedData =>
        isObject(data) && isBoolean(data.cancelled),
    transcription_complete: (data): data is TranscriptionCompleteData =>
        isObject(data) &&
        isString(data.text) &&
        (isNumber(data.id) || data.id === null) &&
        isNumber(data.duration_ms) &&
        isNumber(data.speech_duration_ms),
    transcription_error: (data): data is TranscriptionErrorData =>
        isObject(data) && isString(data.message),
    audio_level: (data): data is AudioLevelData =>
        isObject(data) && isNumber(data.level),
    audio_spectrum: (data): data is AudioSpectrumData =>
        isObject(data) && isNumberArray(data.bands),
    refinement_started: (data): data is RefinementStartedData =>
        isObject(data) && isNumber(data.transcript_id) && isNumber(data.level),
    refinement_complete: (data): data is RefinementCompleteData =>
        isObject(data) &&
        isNumber(data.transcript_id) &&
        isString(data.text) &&
        isNumber(data.level),
    refinement_error: (data): data is RefinementErrorData =>
        isObject(data) &&
        (data.transcript_id === undefined || isNumber(data.transcript_id)) &&
        isString(data.message),
    refinement_progress: (data): data is RefinementProgressData =>
        isObject(data) &&
        isNumber(data.transcript_id) &&
        (data.message === undefined || isString(data.message)) &&
        (data.elapsed_seconds === undefined || isNumber(data.elapsed_seconds)),
    transcript_deleted: (data): data is TranscriptDeletedData =>
        isObject(data) && isNumber(data.id),
    transcript_updated: (data): data is TranscriptUpdatedData =>
        isObject(data) && isNumber(data.id) && isNumber(data.variant_id),
    config_updated: (data): data is ConfigUpdatedData => isObject(data),
    engine_status: (data): data is EngineStatusData =>
        isObject(data) &&
        (data.asr === undefined || isString(data.asr)) &&
        (data.slm === undefined || isString(data.slm)),
    onboarding_required: (data): data is OnboardingRequiredData =>
        isObject(data) && isString(data.reason),
    download_progress: (data): data is DownloadProgressData =>
        isObject(data) &&
        isString(data.model_id) &&
        isDownloadStatus(data.status) &&
        isString(data.message),
    project_created: (data): data is ProjectCreatedData =>
        isObject(data) &&
        isNumber(data.id) &&
        isString(data.name) &&
        (isString(data.color) || data.color === null),
    project_deleted: (data): data is ProjectDeletedData =>
        isObject(data) && isNumber(data.id),
    key_captured: (data): data is KeyCapturedData =>
        isObject(data) && isString(data.combo) && isString(data.display),
    insight_ready: (data): data is InsightReadyData =>
        isObject(data) && isString(data.text),
};
