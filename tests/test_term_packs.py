import pytest

from core import term_packs
from core.term_packs import combined_terms, correct_text, hint_prompt, parse_pack_text

MEDICAL = term_packs.pack_terms("medical")
LEGAL = term_packs.pack_terms("legal")
BUSINESS = term_packs.pack_terms("business")
FUZZY = term_packs.pack_fuzzy_terms("medical")


def test_builtin_packs_are_not_empty():
    assert len(MEDICAL) > 200
    assert len(LEGAL) > 150
    assert len(BUSINESS) > 150


def test_parse_skips_notes_blanks_and_repeats():
    text = "﻿# note\n\nMRI\n  habeas   corpus \nmri\n" + "x" * 80 + "\n"
    assert parse_pack_text(text) == ["MRI", "habeas corpus"]


@pytest.mark.parametrize(
    "heard, expected",
    [
        ("the mri showed nothing", "the MRI showed nothing"),
        ("Started on met formin today", "Started on metformin today"),
        ("She takes lisinipril daily", "She takes lisinopril daily"),
        ("Hypertension is common", "Hypertension is common"),
        ("a myocardial infarction", "a myocardial infarction"),
        ("an Ecg was done", "an ECG was done"),
        ("I started metorfumin and lezenobril.", "I started metformin and lisinopril."),
        ("apixiban and clopidogril", "apixaban and clopidogrel"),
        ("started metformin and lezenobrel.", "started metformin and lisinopril."),
    ],
)
def test_medical_corrections(heard, expected):
    assert correct_text(heard, MEDICAL, FUZZY) == expected


def test_start_of_sentence_capital_is_kept_for_lowercase_terms():
    assert correct_text("Metformin helps.", MEDICAL) == "Metformin helps."
    assert correct_text("Met formin helps.", MEDICAL) == "Metformin helps."


def test_phrase_casing():
    assert correct_text("he filed a habeas corpus petition", LEGAL) == (
        "he filed a habeas corpus petition"
    )
    assert correct_text("sign the nda today", LEGAL) == "sign the NDA today"
    assert correct_text("EBITDA grew, ebitda is up", BUSINESS) == "EBITDA grew, EBITDA is up"


def test_ordinary_sentences_are_left_alone():
    sentences = [
        "I will be in the office or at home, it does not matter.",
        "She said palpitation was the problem and the answer was simple.",
        "We bid on the bun and walked to the er clinic or the operating room.",
        "Please send the report and call me back about the meeting.",
        "The safe is in Sam's room at the tam hotel.",
    ]
    terms = combined_terms(["medical", "legal", "business"], [])
    for sentence in sentences:
        assert correct_text(sentence, terms) == sentence


def test_short_words_are_never_fuzzy_matched():
    assert correct_text("the stroke was mild", ["stroker"]) == "the stroke was mild"


def test_custom_vocabulary_is_corrected_too():
    assert correct_text("hello voxscribe", ["VoxScribe"]) == "hello VoxScribe"


def test_arabic_text_is_untouched():
    text = "هذا اجتماع مهم"
    assert correct_text(text, MEDICAL) == text


def test_nothing_to_do_without_terms():
    assert correct_text("anything", []) == "anything"
    assert correct_text("", ["MRI"]) == ""


def test_combined_terms_put_custom_first_without_repeats():
    terms = combined_terms(["business"], ["Ahmed", "kpi"])
    assert terms[:2] == ["Ahmed", "kpi"]
    assert [t.lower() for t in terms].count("kpi") == 1


def test_hint_prompt_is_short_and_covers_each_pack():
    prompt = hint_prompt(["medical", "legal", "business"], ["Ahmed"])
    assert prompt.startswith("Vocabulary that may come up: Ahmed,")
    assert len(prompt) < 560
    assert "metformin" in prompt
    assert "habeas corpus" in prompt
    assert "EBITDA" in prompt


def test_hint_prompt_none_when_nothing_selected():
    assert hint_prompt([], []) is None


def test_import_and_remove_user_pack(tmp_path, monkeypatch):
    monkeypatch.setattr(term_packs, "USER_DIR", tmp_path / "packs")
    source = tmp_path / "Clinic names.txt"
    source.write_text("# mine\nDr. Okafor\nNorthside Clinic\n", encoding="utf-8")
    pack_id, label, count = term_packs.import_pack(source)
    assert (pack_id, label, count) == ("user:Clinic names", "Clinic names", 2)
    assert term_packs.pack_terms(pack_id) == ["Dr. Okafor", "Northside Clinic"]
    assert any(p[0] == pack_id for p in term_packs.available_packs())
    assert term_packs.remove_user_pack(pack_id)
    assert term_packs.pack_terms(pack_id) == []


def test_import_rejects_empty_and_huge_files(tmp_path, monkeypatch):
    monkeypatch.setattr(term_packs, "USER_DIR", tmp_path / "packs")
    empty = tmp_path / "empty.txt"
    empty.write_text("# only a note\n", encoding="utf-8")
    with pytest.raises(ValueError):
        term_packs.import_pack(empty)
    huge = tmp_path / "huge.txt"
    huge.write_bytes(b"word\n" * 300_000)
    with pytest.raises(ValueError):
        term_packs.import_pack(huge)


def test_unknown_pack_id_has_no_terms():
    assert term_packs.pack_terms("nope") == []
    assert term_packs.pack_terms("user:../../evil") == []


def test_fuzzy_repair_only_reaches_marked_drug_names():
    terms = combined_terms(["medical", "legal", "business"], [])
    fuzzy = term_packs.combined_fuzzy_terms(["medical", "legal", "business"])
    assert "metformin" in fuzzy
    assert "depression" not in fuzzy and "litigation" not in fuzzy
    for sentence in [
        "Her expression showed relief and the complaints stopped.",
        "The evaluation and mitigation plan covers permission and discovery.",
        "The valuation of the contract depends on the validation step.",
    ]:
        assert correct_text(sentence, terms, fuzzy) == sentence


def test_without_fuzzy_terms_misspellings_stay():
    assert correct_text("lisinipril", MEDICAL) == "lisinipril"


def test_parse_pack_reads_fuzzy_sections():
    text = "\n".join(["a", "# fuzzy: on", "rarex", "# fuzzy: off", "common"])
    terms, fuzzy = term_packs.parse_pack(text)
    assert terms == ["a", "rarex", "common"]
    assert fuzzy == ["rarex"]


def test_capital_inside_a_sentence_is_lowered_for_lowercase_terms():
    assert correct_text("We gave Azithromycin today.", MEDICAL) == "We gave azithromycin today."
    assert correct_text("Done. Azithromycin next.", MEDICAL) == "Done. Azithromycin next."
    assert correct_text("Plan:\nAzithromycin daily", MEDICAL) == "Plan:\nAzithromycin daily"


ALL = ["medical", "legal", "business"]


@pytest.mark.parametrize(
    "heard, expected",
    [
        ("a chest X ray today", "a chest X-ray today"),
        ("tracking C A C and ARR", "tracking CAC and ARR"),
        ("ordered a C B C", "ordered a CBC"),
        ("given amoxillin daily", "given amoxicillin daily"),
        ("discuss the indomcification clause", "discuss the indemnification clause"),
        ("a laparoscopy and a colonoscopy", "a laparoscopy and a colonoscopy"),
        ("she had a colonoscopi", "she had a colonoscopy"),
    ],
)
def test_second_round_corrections(heard, expected):
    terms = combined_terms(ALL, [])
    fuzzy = term_packs.combined_fuzzy_terms(ALL)
    assert correct_text(heard, terms, fuzzy) == expected


def test_pack_fuzzy_blocks_hold_only_rare_words():
    fuzzy = {t.lower() for p in ALL for t in term_packs.pack_fuzzy_terms(p)}
    assert {"colonoscopy", "indemnification", "metformin"} <= fuzzy
    assert not {"depression", "litigation", "valuation", "paracentesis"} & fuzzy


def test_two_neighbouring_letters_swapped_in_a_drug_name():
    terms = combined_terms(["medical"], [])
    fuzzy = term_packs.combined_fuzzy_terms(["medical"])
    assert correct_text("on atrovastatine daily", terms, fuzzy) == "on atorvastatin daily"
