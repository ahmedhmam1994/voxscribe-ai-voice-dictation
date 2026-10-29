import pytest

from core import term_packs, voice_teach
from core.voice_teach import Slip, build_script, find_slips, merge


@pytest.mark.parametrize("pack", ["medical", "legal", "business"])
def test_every_target_is_a_term_of_its_pack_and_is_in_its_sentence(pack):
    terms = {t.lower() for t in term_packs.pack_terms(pack)}
    for sentence, targets in voice_teach.SENTENCES[pack]:
        for target in targets:
            assert target.lower() in terms, (pack, target)
            assert voice_teach._find(voice_teach._words(sentence), voice_teach._words(target)) >= 0


def test_script_alternates_packs_and_ends_with_custom_vocabulary():
    script = build_script(["medical", "legal"], ["Okafor", "Northside"], length=6)
    sentences = [s for s, _ in script]
    assert sentences[0] == voice_teach.SENTENCES["medical"][0][0]
    assert sentences[1] == voice_teach.SENTENCES["legal"][0][0]
    assert len(script) == 6
    assert script[-1] == ("Today I will talk about Okafor and Northside.", ["Okafor", "Northside"])


def test_script_uses_builtin_packs_when_none_enabled():
    script = build_script([], [], length=3)
    assert len(script) == 3


def test_sentence_heard_right_has_no_slips():
    sentence, targets = voice_teach.SENTENCES["medical"][1]
    heard = "The doctor ordered a CBC and HbA1c and a chest X ray."
    assert find_slips(sentence, targets, heard) == []


def test_misheard_terms_become_slips():
    sentence, targets = voice_teach.SENTENCES["medical"][4]
    heard = "TSH was high so we started levoseroxine for hypoceroxidism."
    assert find_slips(sentence, targets, heard) == [
        Slip("levoseroxine", "levothyroxine"),
        Slip("hypoceroxidism", "hypothyroidism"),
    ]


def test_multi_word_term_slip():
    sentence, targets = voice_teach.SENTENCES["legal"][2]
    heard = "The lawyer cited habeas corpus and the status of the limitation."
    assert find_slips(sentence, targets, heard) == [
        Slip("status of the limitation", "statute of limitations")
    ]


def test_a_garbled_neighbourhood_is_skipped_not_guessed():
    sentence, targets = voice_teach.SENTENCES["medical"][0]
    heard = "Something completely different was said here."
    assert find_slips(sentence, targets, heard) == []


def test_heard_phrase_that_is_another_known_term_is_not_proposed():
    sentence, targets = voice_teach.SENTENCES["business"][2]
    heard = "We are tracking CAC and ARR and churn for the board meeting."
    assert find_slips(sentence, targets, heard, known_terms=["churn"]) == []
    heard = "We are tracking CAC and ARR and KPI for the board meeting."
    assert find_slips(sentence, targets, heard, known_terms=["KPI"]) == []


def test_short_or_stopword_heard_text_is_ignored():
    sentence, targets = voice_teach.SENTENCES["business"][1]
    assert find_slips(sentence, targets, "The client wants to renew the SLA before the end of it.") == []


def test_empty_heard_text():
    assert find_slips("A b c", ["b"], "") == []


def test_merge_counts_repeats_and_orders_them_first():
    merged = merge(
        [
            [Slip("chern", "churn")],
            [Slip("kbi", "KPI"), Slip("chern", "churn")],
        ]
    )
    assert [(p.heard, p.expected, p.count) for p in merged] == [
        ("chern", "churn", 2),
        ("kbi", "KPI", 1),
    ]
