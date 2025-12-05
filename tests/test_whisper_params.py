from chatterbug.domain.model import EngineConfig, TranscriptionOptions
from chatterbug.engines.whisper_turbo import WhisperTurboEngine


def test_whisper_merges_params():
    cfg = EngineConfig(params={"enable_batching": "false", "word_timestamps": "true"})
    engine = WhisperTurboEngine(cfg)
    opts = TranscriptionOptions(params={"word_timestamps": "false"})
    merged = {**cfg.params, **opts.params}
    assert merged["word_timestamps"] == "false"

