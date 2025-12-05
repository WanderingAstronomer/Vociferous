from dataclasses import dataclass

@dataclass
class Metrics:
    audio_queue_depth: int = 0
    segment_queue_depth: int = 0
    inference_latency_ms: float = 0.0

# Global metrics singleton
metrics = Metrics()
