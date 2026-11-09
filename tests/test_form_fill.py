"""core/form_fill.py: the same cases as the Android app's FormFillTest.kt."""

from core import form_fill as ff
from core.form_fill import EMAIL, PHONE, TEXT, Field

CONTACT = [
    Field(0, "Name", TEXT),
    Field(1, "Phone", PHONE),
    Field(2, "Email", EMAIL),
    Field(3, "City", TEXT),
]


def fills(spoken: str, fields: list[Field] = CONTACT) -> dict[int, str] | None:
    planned = ff.plan(spoken, fields)
    return None if planned is None else {f.index: f.value for f in planned}


def test_fills_every_named_box():
    assert fills(
        "Name Sam Lee, phone 0100 123 4567, email Sam at gmail dot com, city Cairo."
    ) == {0: "Sam Lee", 1: "01001234567", 2: "sam@gmail.com", 3: "Cairo"}


def test_ordinary_dictation_is_left_alone():
    assert fills("Call me on my phone when you reach the city.") is None
    assert fills("Name Sam Lee.") is None
    assert fills("") is None


def test_a_short_lead_in_is_allowed():
    assert fills("My name is Sam and city is Cairo") == {0: "Sam", 3: "Cairo"}
    assert fills("Please name Sam, city Cairo") is None


def test_labels_match_their_common_words():
    fields = [
        Field(0, "First name *", TEXT),
        Field(1, "Last name", TEXT),
        Field(2, "Mobile number (optional)", PHONE),
        Field(3, "Enter your e-mail:", EMAIL),
    ]
    assert fills(
        "first name Sam surname Lee phone oh one oh oh email sam at x dot com", fields
    ) == {0: "Sam", 1: "Lee", 2: "0100", 3: "sam@x.com"}


def test_longest_label_wins():
    fields = [Field(0, "Name"), Field(1, "First name")]
    assert fills("first name Sam, name Sam Lee", fields) == {1: "Sam", 0: "Sam Lee"}


def test_two_boxes_with_the_same_label_fill_in_screen_order():
    fields = [Field(0, "Phone", PHONE), Field(1, "Phone", PHONE)]
    assert fills("phone 111 phone 222", fields) == {0: "111", 1: "222"}


def test_unlabelled_boxes_are_ignored():
    assert fills("name Sam city Cairo", [Field(0, ""), Field(1, "Name")]) is None


def test_a_label_that_is_not_a_common_phrase_stays_itself():
    assert ff.aliases("Name of pet") == {"name of pet"}
    assert "mobile" in ff.aliases("Phone number")
    assert ff.aliases("*") == set()


def test_a_full_name_splits_into_first_and_last_name_boxes():
    fields = [
        Field(0, "First name"),
        Field(1, "Last name"),
        Field(2, "Company"),
        Field(3, "Phone (Mobile)", PHONE),
    ]
    assert fills(
        "Name Sam Lee, phone 0100 123 4567, email sam at gmail dot com", fields
    ) == {0: "Sam", 1: "Lee", 3: "01001234567"}
    assert fills("first name Sam Ann last name Lee", fields) == {0: "Sam Ann", 1: "Lee"}


def test_a_name_box_keeps_the_whole_name():
    fields = [Field(0, "Name"), Field(1, "Last name")]
    assert fills("name Sam Lee, last name Lee", fields) == {0: "Sam Lee", 1: "Lee"}


def test_a_web_form_answers_to_its_common_words():
    fields = [
        Field(0, "Customer name:"),
        Field(1, "Telephone:", PHONE),
        Field(2, "E-mail address:", EMAIL),
        Field(3, "Delivery instructions:"),
    ]
    assert fills(
        "Name Sam Lee, phone 0100 123 4567, email sam at gmail dot com, "
        "delivery instructions ring twice",
        fields,
    ) == {0: "Sam Lee", 1: "01001234567", 2: "sam@gmail.com", 3: "ring twice"}
    assert ff.aliases("User name") == {"user name"}


def test_a_form_sentence_is_known_before_reading_the_window():
    assert ff.starts_like_a_form("Name Sam Lee, company Acme, phone 0100")
    assert not ff.starts_like_a_form("Call me on my phone when you reach the city.")
    assert not ff.starts_like_a_form("Name Sam Lee.")


def test_automation_ids_become_labels():
    assert ff.label_from_id("et_phone_number") == "phone number"
    assert ff.label_from_id("inputEmail") == "email"
    assert ff.label_from_id("com.app:id/et") is None
    assert ff.label_from_id(None) is None


def test_values_lose_connectors_and_punctuation():
    assert ff.clean_value(" is Sam Lee, and", TEXT) == "Sam Lee"
    assert ff.clean_value(" sam at gmail dot com.", EMAIL) == "sam@gmail.com"


def test_kind_comes_from_the_label():
    assert ff.kind_of_label("E-mail address:") == EMAIL
    assert ff.kind_of_label("Mobile number") == PHONE
    assert ff.kind_of_label("Your website") == ff.URL
    assert ff.kind_of_label("City") == TEXT


def test_spoken_dates_are_read_with_the_month_named():
    assert ff.parse_date("5 March 1990") == (1990, 3, 5)
    assert ff.parse_date("March 5th, 1990") == (1990, 3, 5)
    assert ff.parse_date("the twenty first of June 2001") == (2001, 6, 21)
    assert ff.parse_date("2nd Jan 2001") == (2001, 1, 2)
    assert ff.parse_date("5/3/1990") is None
    assert ff.parse_date("next Tuesday") is None


def test_a_date_goes_in_the_form_the_box_wants():
    assert ff.format_date("5 March 1990", "MDY") == "03051990"
    assert ff.format_date("5 March 1990", "DMY") == "05031990"
    assert ff.format_date("5 March 1990", "DD/MM/YYYY") == "05/03/1990"
    assert ff.format_date("5 March 1990", "YYYY-MM-DD") == "1990-03-05"
    assert ff.format_date("5 March 1990", "") == "5 March 1990"
    # A date picker never gets text it cannot use.
    assert ff.format_date("sometime soon", "MDY") == ""
    assert ff.format_date("sometime soon", "DD/MM/YYYY") == "sometime soon"


def test_date_hints_show_the_pattern():
    assert ff.date_pattern("DD/MM/YYYY") == "DD/MM/YYYY"
    assert ff.date_pattern("e.g. mm-dd-yyyy") == "MM-DD-YYYY"
    assert ff.date_pattern("Your name") == ""


def test_a_form_with_a_dropdown_and_a_date_picker():
    fields = [
        Field(0, "Full name"),
        Field(1, "Country", ff.CHOICE),
        Field(2, "Date of birth", ff.DATE, "MDY"),
        Field(3, "Appointment date", ff.DATE, "DD/MM/YYYY"),
    ]
    assert fills(
        "Name Sam Lee, country Egypt, date of birth 5 March 1990, "
        "appointment date the 2nd of January 2027.",
        fields,
    ) == {0: "Sam Lee", 1: "Egypt", 2: "03051990", 3: "02/01/2027"}


def test_a_label_with_no_box_still_ends_the_value_before_it():
    fields = [Field(0, "Full name"), Field(1, "Email", EMAIL)]
    assert fills(
        "Name Sam Lee, country Egypt, email sam at gmail dot com, city Cairo.", fields
    ) == {0: "Sam Lee", 1: "sam@gmail.com"}
    # Without a comma it is part of what was said: "a note about my address".
    assert fills(
        "name Sam Lee, message a note about my address", [Field(0, "Name"), Field(1, "Message")]
    ) == {0: "Sam Lee", 1: "a note about my address"}
