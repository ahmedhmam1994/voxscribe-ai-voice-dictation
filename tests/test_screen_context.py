from core import screen_context as sc
from core import term_packs


def test_file_and_project_names_come_out_of_an_editor_title():
    terms = sc.terms_from_title("budget_report.py - Northwind - Visual Studio Code")
    assert "budget_report" in terms and "Northwind" in terms
    assert "Visual" not in terms and "Code" not in terms


def test_the_program_name_at_the_end_is_dropped():
    assert sc.terms_from_title("Kowalczyk contract draft - Google Chrome") == ["Kowalczyk"]


def test_plain_words_and_page_words_are_not_hints():
    assert sc.terms_from_title("new tab") == []
    assert sc.terms_from_title("Inbox - Gmail") == []
    assert sc.terms_from_title("") == []


def test_the_apps_own_name_is_not_a_hint():
    assert sc.terms_from_title("VoxScribe - Settings") == []


def test_the_list_is_capped():
    title = " ".join(f"Name{i}x" for i in range(20)) + " - App"
    assert len(sc.terms_from_title(title)) == sc.MAX_TERMS


def test_context_words_go_into_the_hint_after_custom_words():
    prompt = term_packs.hint_prompt([], ["Priya"], ["Northwind", "priya"])
    assert prompt == "Vocabulary that may come up: Priya, Northwind."


def test_the_hint_stays_within_its_length_with_context():
    long_ctx = [f"Contextword{i}" for i in range(60)]
    prompt = term_packs.hint_prompt([], [], long_ctx)
    assert prompt is not None and len(prompt) <= term_packs.PROMPT_CHARS + 40
