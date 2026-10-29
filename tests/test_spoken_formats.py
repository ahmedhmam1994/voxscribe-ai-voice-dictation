import pytest

from core.spoken_formats import apply_spoken_formats, spoken_int

MED = ["medical"]
LAW = ["legal"]
BIZ = ["business"]
ALL = ["medical", "legal", "business"]


@pytest.mark.parametrize(
    "phrase, value",
    [
        ("one hundred and five", 105),
        ("a hundred", 100),
        ("one twenty", 120),
        ("one forty five", 145),
        ("two ten", 210),
        ("eighty", 80),
        ("fifty thousand", 50000),
        ("one", 1),
        ("banana", None),
        ("twenty twenty", None),
    ],
)
def test_spoken_int(phrase, value):
    assert spoken_int(phrase) == value


@pytest.mark.parametrize(
    "spoken, written",
    [
        ("blood pressure one twenty over eighty today", "blood pressure 120/80 today"),
        ("one hundred and thirty over eighty five", "130/85"),
        ("a hundred and ten over seventy", "110/70"),
        ("five milligrams twice daily", "5 mg BID"),
        ("take ten milligrams by mouth every eight hours", "take 10 mg PO q8h"),
        ("two point five milligrams three times a day", "2.5 mg TID"),
        ("point five milligrams as needed", "0.5 mg PRN"),
        ("two hundred micrograms", "200 mcg"),
        ("five hundred milliliters of saline", "500 mL of saline"),
        ("oxygen saturation ninety eight percent", "oxygen saturation 98%"),
    ],
)
def test_medical_formats(spoken, written):
    assert apply_spoken_formats(spoken, MED) == written


@pytest.mark.parametrize(
    "spoken",
    [
        "one over two of the team agreed",
        "I walked three miles twice daily",
        "she took one of them",
        "the score was ten over four hundred",
        "fifty over thirty five",
    ],
)
def test_medical_formats_leave_ordinary_text_alone(spoken):
    assert apply_spoken_formats(spoken, MED) == spoken


@pytest.mark.parametrize(
    "spoken, written",
    [
        ("section twelve subsection b", "section 12(b)"),
        ("Section twelve subsection b subsection two", "Section 12(b)(2)"),
        ("see article five", "see article 5"),
        ("clause four point two applies", "clause 4.2 applies"),
        ("paragraph three of the agreement", "paragraph 3 of the agreement"),
        ("Smith versus Jones was decided", "Smith v. Jones was decided"),
    ],
)
def test_legal_formats(spoken, written):
    assert apply_spoken_formats(spoken, LAW) == written


def test_legal_versus_needs_names():
    assert apply_spoken_formats("cats versus dogs", LAW) == "cats versus dogs"


@pytest.mark.parametrize(
    "spoken, written",
    [
        ("fifty thousand dollars", "$50,000"),
        ("two point five million dollars", "$2.5 million"),
        ("one hundred and five dollars", "$105"),
        ("a budget of three million euros", "a budget of €3 million"),
        ("growth of twenty percent", "growth of 20%"),
        ("results for q three", "results for Q3"),
        ("Q four planning", "Q4 planning"),
    ],
)
def test_business_formats(spoken, written):
    assert apply_spoken_formats(spoken, BIZ) == written


def test_a_pack_only_formats_its_own_things():
    assert apply_spoken_formats("five milligrams", LAW) == "five milligrams"
    assert apply_spoken_formats("section twelve", MED) == "section twelve"
    assert apply_spoken_formats("fifty thousand dollars", MED) == "fifty thousand dollars"


def test_nothing_without_packs_or_text():
    assert apply_spoken_formats("five milligrams", []) == "five milligrams"
    assert apply_spoken_formats("", ALL) == ""


def test_all_packs_together():
    text = "one twenty over eighty and section nine and fifty thousand dollars"
    assert apply_spoken_formats(text, ALL) == "120/80 and section 9 and $50,000"


@pytest.mark.parametrize(
    "spoken, written",
    [
        ("Blood pressure on 20 over 80, 5 milligrams twice daily", "Blood pressure 120/80, 5 mg BID"),
        ("blood pressure one 40 over 90", "blood pressure 140/90"),
        ("pressure 120 over 80 today", "pressure 120/80 today"),
        ("take 10 milligrams by mouth every 8 hours", "take 10 mg PO q8h"),
        ("2.5 milligrams three times a day", "2.5 mg TID"),
        ("500 milliliters of saline", "500 mL of saline"),
        ("oxygen saturation 98 percent", "oxygen saturation 98%"),
        ("1,000 micrograms", "1000 mcg"),
    ],
)
def test_digits_written_by_the_speech_model(spoken, written):
    assert apply_spoken_formats(spoken, MED) == written


@pytest.mark.parametrize(
    "spoken",
    [
        "5 over 3 was the score",
        "it was on 20 over time",
        "20 over 80 degrees is not a pressure",
        "I have 5 minutes",
    ],
)
def test_digits_in_ordinary_text_stay(spoken):
    assert apply_spoken_formats(spoken, MED) == spoken


def test_digits_in_law_and_business():
    assert apply_spoken_formats("see section 12 subsection b", LAW) == "see section 12(b)"
    assert apply_spoken_formats("clause 4.2 applies", LAW) == "clause 4.2 applies"
    assert apply_spoken_formats("a fee of 50000 dollars", BIZ) == "a fee of $50,000"
    assert apply_spoken_formats("it cost 2.5 million dollars", BIZ) == "it cost $2.5 million"
    assert apply_spoken_formats("growth of 20 percent", BIZ) == "growth of 20%"
