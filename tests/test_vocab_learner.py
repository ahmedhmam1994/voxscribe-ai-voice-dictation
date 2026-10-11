"""Tests for core/vocab_learner.py: picking vocabulary out of a user's files."""

from core.vocab_learner import extract_terms, learn_from_folder, merge_vocabulary


def test_identifiers_acronyms_and_digit_words_are_found():
    text = "The getUserName helper and max_retry_count use HTTP with Whisper3 today."
    terms = extract_terms(text)

    assert {"getUserName", "max_retry_count", "HTTP", "Whisper3"} <= set(terms)


def test_ordinary_words_are_not_terms():
    assert not extract_terms("the quick brown fox jumps over the lazy dog")


def test_a_capitalized_word_at_the_start_of_a_sentence_is_ignored():
    assert "Tomorrow" not in extract_terms("Tomorrow we ship. Then we rest.")


def test_a_capitalized_word_mid_sentence_is_a_name():
    assert "Ahmed" in extract_terms("We asked Ahmed about it.")


def test_common_capitalized_words_are_ignored():
    assert not extract_terms("We know That This will work, and When it does.")


def test_learning_needs_a_term_twice(tmp_path):
    (tmp_path / "notes.md").write_text(
        "We use Kubernetes daily. Ask Kubernetes folks. Once mentioned Zebulon only.",
        encoding="utf-8",
    )

    learned = learn_from_folder(tmp_path)

    assert "Kubernetes" in learned
    assert "Zebulon" not in learned


def test_other_file_types_and_skipped_folders_are_left_alone(tmp_path):
    (tmp_path / "photo.png").write_bytes(b"CamelCaseThing CamelCaseThing")
    skipped = tmp_path / "node_modules"
    skipped.mkdir()
    (skipped / "lib.js").write_text("hiddenHelper hiddenHelper", encoding="utf-8")

    assert learn_from_folder(tmp_path) == []


def test_a_missing_folder_learns_nothing(tmp_path):
    assert learn_from_folder(tmp_path / "nope") == []


def test_merge_keeps_existing_terms_first_and_skips_repeats():
    merged = merge_vocabulary(["VoxScribe", "Ahmed"], ["ahmed", "Kubernetes", "VoxScribe"])

    assert merged == ["VoxScribe", "Ahmed", "Kubernetes"]
