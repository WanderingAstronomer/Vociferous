/**
 * Vociferous WebSocket client for real-time events.
 */

import {
    wsEventValidators,
    type WSEventType,
    type TypedEventHandler,
} from "./events";

export type EventHandler = (data: unknown) => void;

const isObject = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

class WSClient {
    private ws: WebSocket | null = null;
    private handlers = new Map<string, Set<EventHandler>>();
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private reconnectDelay = 1000;
    private maxReconnectDelay = 30000;
    private disposed = false;

    connect(): void {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${location.host}/ws`;

        try {
            this.ws = new WebSocket(url);
            this.ws.onopen = () => {
                this.reconnectDelay = 1000;
            };
            this.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data) as unknown;
                    if (!isObject(msg)) {
                        console.warn("[ws] invalid message payload", event.data);
                        return;
                    }

                    const type = msg.type;
                    if (typeof type !== "string") {
                        console.warn("[ws] missing event type", msg);
                        return;
                    }

                    const data = msg.data;
                    if (type in wsEventValidators) {
                        const validator = wsEventValidators[type as WSEventType];
                        if (!validator(data)) {
                            console.warn("[ws] invalid event payload", type, data);
                            return;
                        }
                    }

                    const handlers = this.handlers.get(type);
                    if (handlers) {
                        for (const handler of handlers) {
                            handler(data);
                        }
                    }
                } catch {
                    console.warn("[ws] invalid message", event.data);
                }
            };
            this.ws.onclose = () => {
                this.scheduleReconnect();
            };
            this.ws.onerror = () => {
                this.ws?.close();
            };
        } catch {
            this.scheduleReconnect();
        }
    }

    /**
     * Subscribe to a typed WebSocket event.
     * Returns an unsubscribe function.
     */
    on<T extends WSEventType>(type: T, handler: TypedEventHandler<T>): () => void;
    on(type: string, handler: EventHandler): () => void;
    on(type: string, handler: EventHandler): () => void {
        if (!this.handlers.has(type)) {
            this.handlers.set(type, new Set());
        }
        this.handlers.get(type)!.add(handler);
        return () => this.handlers.get(type)?.delete(handler);
    }

    send(type: string, data: unknown = {}): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type, data }));
        }
    }

    disconnect(): void {
        this.disposed = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this.ws?.close();
        this.ws = null;
    }

    private scheduleReconnect(): void {
        if (this.disposed || this.reconnectTimer) return;
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
            this.connect();
        }, this.reconnectDelay);
    }
}

export const ws = new WSClient();
