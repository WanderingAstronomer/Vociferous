import { getConfig, updateConfig } from "./api";
import type { ConfigUpdatedData } from "./events";
import { ws } from "./ws";

export interface VociferousConfig {
    model?: {
        provider?: "local_faster_whisper" | "groq";
        model?: string;
        device?: string;
        language?: string;
        n_threads?: number;
        compute_type?: string;
        initial_prompt?: string;
        groq?: {
            base_url?: string;
            model_id?: string;
            api_key_env?: string | null;
            api_key?: string | null;
            timeout_seconds?: number;
            model_list_enabled?: boolean;
            temperature?: number;
            max_retries?: number;
            retry_backoff_seconds?: number;
        };
    };
    recording?: {
        activation_key?: string;
        hotkey_backend?: string;
        recording_mode?: string;
        sample_rate?: number;
        min_duration_ms?: number;
        max_recording_minutes?: number;
        audio_cache_minutes?: number;
        vad_sensitivity?: string;
    };
    user?: {
        name?: string;
        typing_wpm?: number;
        page_size?: number;
    };
    logging?: {
        level?: string;
        console_echo?: boolean;
        structured_output?: boolean;
    };
    output?: {
        add_trailing_space?: boolean;
        auto_copy_to_clipboard?: boolean;
        auto_retitle_on_refine?: boolean;
        auto_refine?: boolean;
        exclude_imported_from_analytics?: boolean;
    };
    safety?: {
        confirm_delete?: boolean;
    };
    refinement?: {
        enabled?: boolean;
        provider?: "local_ct2" | "lm_studio" | "groq";
        model_id?: string;
        n_gpu_layers?: number;
        n_threads?: number;
        use_thinking?: boolean;
        temperature?: number;
        top_p?: number;
        top_k?: number;
        repetition_penalty?: number;
        system_prompt?: string;
        invariants?: string[];
        default_prompt_transcript_id?: number | null;
        lm_studio?: {
            base_url?: string;
            model_id?: string;
            api_key_env?: string | null;
            api_key?: string | null;
            timeout_seconds?: number;
            max_output_tokens?: number;
            model_list_enabled?: boolean;
        };
        groq?: {
            base_url?: string;
            model_id?: string;
            api_key_env?: string | null;
            api_key?: string | null;
            timeout_seconds?: number;
            max_output_tokens?: number;
            model_list_enabled?: boolean;
            max_retries?: number;
            retry_backoff_seconds?: number;
        };
    };
    display?: {
        ui_scale?: number;
    };
    [key: string]: unknown;
}

export interface ConfigValueByPath {
    "display.ui_scale": number;
    "logging.level": string;
    "model.device": string;
    "model.language": string;
    "model.model": string;
    "model.n_threads": number;
    "model.provider": "local_faster_whisper" | "groq";
    "model.groq.base_url": string;
    "model.groq.model_id": string;
    "model.groq.api_key_env": string | null;
    "model.groq.api_key": string | null;
    "model.groq.timeout_seconds": number;
    "model.groq.model_list_enabled": boolean;
    "model.groq.temperature": number;
    "model.groq.max_retries": number;
    "model.groq.retry_backoff_seconds": number;
    "output.add_trailing_space": boolean;
    "output.auto_copy_to_clipboard": boolean;
    "output.auto_refine": boolean;
    "output.auto_retitle_on_refine": boolean;
    "output.exclude_imported_from_analytics": boolean;
    "recording.activation_key": string;
    "recording.audio_cache_minutes": number;
    "recording.max_recording_minutes": number;
    "recording.recording_mode": string;
    "refinement.enabled": boolean;
    "refinement.provider": "local_ct2" | "lm_studio" | "groq";
    "refinement.model_id": string;
    "refinement.n_gpu_layers": number;
    "refinement.n_threads": number;
    "refinement.repetition_penalty": number;
    "refinement.temperature": number;
    "refinement.top_k": number;
    "refinement.top_p": number;
    "refinement.use_thinking": boolean;
    "refinement.lm_studio.base_url": string;
    "refinement.lm_studio.model_id": string;
    "refinement.lm_studio.api_key_env": string | null;
    "refinement.lm_studio.api_key": string | null;
    "refinement.lm_studio.timeout_seconds": number;
    "refinement.lm_studio.max_output_tokens": number;
    "refinement.lm_studio.model_list_enabled": boolean;
    "refinement.groq.base_url": string;
    "refinement.groq.model_id": string;
    "refinement.groq.api_key_env": string | null;
    "refinement.groq.api_key": string | null;
    "refinement.groq.timeout_seconds": number;
    "refinement.groq.max_output_tokens": number;
    "refinement.groq.model_list_enabled": boolean;
    "refinement.groq.max_retries": number;
    "refinement.groq.retry_backoff_seconds": number;
    "safety.confirm_delete": boolean;
    "user.name": string;
    "user.typing_wpm": number;
}

export type ConfigPath = keyof ConfigValueByPath;
export type ConfigValue<Path extends ConfigPath> = ConfigValueByPath[Path];
export type GetConfigValue = {
    <Path extends ConfigPath>(config: VociferousConfig, path: Path): ConfigValue<Path> | undefined;
    <Path extends ConfigPath>(config: VociferousConfig, path: Path, fallback: ConfigValue<Path>): ConfigValue<Path>;
};
export type SetConfigValue = <Path extends ConfigPath>(path: Path, value: ConfigValue<Path>) => void;

let current = $state<VociferousConfig | null>(null);
let loadPromise: Promise<VociferousConfig> | null = null;
let subscribed = false;

function asConfig(value: Record<string, unknown>): VociferousConfig {
    return value as VociferousConfig;
}

function apply(config: Record<string, unknown>): VociferousConfig {
    current = asConfig(config);
    return current;
}

function ensureSubscribed(): void {
    if (subscribed) return;
    subscribed = true;
    ws.on("config_updated", (data: ConfigUpdatedData) => {
        apply(data);
    });
}

async function ensureLoaded(): Promise<VociferousConfig> {
    ensureSubscribed();
    if (current) return current;
    if (!loadPromise) {
        loadPromise = getConfig()
            .then(apply)
            .finally(() => {
                loadPromise = null;
            });
    }
    return loadPromise;
}

async function refresh(): Promise<VociferousConfig> {
    ensureSubscribed();
    return getConfig().then(apply);
}

async function update(updates: Record<string, unknown>): Promise<VociferousConfig> {
    ensureSubscribed();
    return updateConfig(updates).then(apply);
}

export const appConfig = {
    get current(): VociferousConfig | null {
        return current;
    },
    apply,
    ensureLoaded,
    refresh,
    update,
};