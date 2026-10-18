from core import settings, transcribe


def test_every_model_in_settings_has_a_download_size():
    for size, _ in settings.AVAILABLE_MODEL_SIZES:
        assert size in transcribe.MODEL_APPROX_MB


def test_the_free_models_are_the_three_fastest():
    free = [
        size for size, _ in settings.AVAILABLE_MODEL_SIZES if size not in settings.PRO_MODEL_SIZES
    ]
    assert free == ["tiny", "base", "small"]
    assert settings.DEFAULT_MODEL_SIZE in free


def test_pro_labels_say_pro_and_free_labels_do_not():
    for size, label in settings.AVAILABLE_MODEL_SIZES:
        assert label.endswith("(Pro)") == (size in settings.PRO_MODEL_SIZES)


def test_large_turbo_is_offered_and_marked_as_unable_to_translate():
    sizes = [size for size, _ in settings.AVAILABLE_MODEL_SIZES]
    assert "large-v3-turbo" in sizes
    assert settings.NO_TRANSLATE_MODEL_SIZES <= set(sizes)


def test_large_turbo_label_does_not_promise_speed():
    # "turbo" is only quick next to full Large; on the processor it is much
    # slower than Small, and the label has to say so.
    label = dict(settings.AVAILABLE_MODEL_SIZES)["large-v3-turbo"]
    assert "slower than Small" in label
    assert "quicker" not in label.lower()
