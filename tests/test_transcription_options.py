from chatterbug.domain.model import TranscriptionOptions


def test_transcription_options_params_override() -> None:
    opts = TranscriptionOptions(params={"word_timestamps": "true"})
    assert opts.params["word_timestamps"] == "true"
