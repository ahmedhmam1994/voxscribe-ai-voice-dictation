import pytest
from PySide6.QtCore import QSettings

from core import assistant


@pytest.fixture(autouse=True)
def store(monkeypatch, tmp_path):
    ini = str(tmp_path / "settings.ini")
    monkeypatch.setattr(assistant, "_settings", lambda: QSettings(ini, QSettings.Format.IniFormat))
    return tmp_path


@pytest.mark.parametrize(
    ("spoken", "command"),
    [
        ("Make it formal.", "formal"),
        ("make that more professional", "formal"),
        ("Fix the grammar", "grammar"),
        ("fix grammar in that", "grammar"),
        ("Make it shorter!", "shorter"),
        ("shorten that", "shorter"),
        ("Bullet points.", "bullets"),
        ("turn it into bullet points", "bullets"),
        ("make it friendly", "friendly"),
    ],
)
def test_whole_utterance_commands(spoken, command):
    assert assistant.get_command(spoken) == command


@pytest.mark.parametrize(
    "spoken",
    [
        "we need to make it formal before Friday",
        "the bullet points are wrong",
        "please fix the grammar in my essay tomorrow",
        "",
    ],
)
def test_sentences_with_the_words_stay_dictation(spoken):
    assert assistant.get_command(spoken) is None


def test_messages_carry_the_rules_and_the_text():
    messages = assistant.build_messages("hi mark", "formal")
    assert messages[0]["role"] == "system" and "[Your Name]" in messages[0]["content"]
    assert messages[1]["content"].endswith("Text:\nhi mark")


def test_clean_reply_drops_wrapping():
    assert assistant.clean_reply("<think>hmm</think>\nHello.") == "Hello."
    assert assistant.clean_reply("Here is the formal version:\nDear Mark.") == "Dear Mark."
    assert assistant.clean_reply('"Hello there."') == "Hello there."
    assert assistant.clean_reply("Thanks,\n[Your Name]") == "Thanks,"


def test_a_changed_number_is_never_typed():
    original = "she was given 50 micrograms at 8 and her pressure was 142 over 90"
    assert assistant.check_reply(original, "Given 50 mcg at 08:00; BP 142/90.") is None
    assert "number" in assistant.check_reply(original, "Given 5 mcg at 8; BP 142/90.")


def test_unusable_replies_are_refused():
    assert assistant.check_reply("hello", "") is not None
    assert assistant.check_reply("hello", "Dear [Recipient], hello") is not None
    assert assistant.check_reply("hi", "word " * 200) is not None


def test_folder_and_model_settings(store):
    assert assistant.get_folder() == assistant.DEFAULT_FOLDER
    assistant.set_folder(store / "llm")
    assert assistant.get_folder() == store / "llm"
    assistant.set_model_id("nonsense")
    assert assistant.get_model_id() == assistant.DEFAULT_MODEL
    assistant.set_model_id("gemma-4-e4b")
    assert assistant.model_path().name == "gemma-4-E4B-it-Q4_K_M.gguf"


def test_nothing_is_ready_in_an_empty_folder(store):
    assistant.set_folder(store / "llm")
    assert not assistant.is_ready()
    expected = assistant.MODELS[assistant.DEFAULT_MODEL].size + sum(
        r.size for r in assistant.RUNTIMES.values()
    )
    assert assistant.download_bytes() == expected


def test_assistant_needs_a_download_first(store):
    assistant.set_folder(store / "llm")
    with pytest.raises(assistant.AssistantError, match="Download"):
        assistant.Assistant().rewrite("hello", "formal")
