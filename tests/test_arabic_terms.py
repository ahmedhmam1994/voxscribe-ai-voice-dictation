from core.arabic_terms import apply_arabic_terms


def test_swaps_listed_words_and_keeps_the_rest():
    text = "بعد الميتنج بتاع الساعه اربعه هبعتلك الريبورت"
    assert apply_arabic_terms(text) == "بعد الـ meeting بتاع الساعه اربعه هبعتلك الـ report"


def test_plain_word_without_the_article():
    assert apply_arabic_terms("لازم نعمل ابدات") == "لازم نعمل update"


def test_spelling_variants_match():
    # Hamza forms, ya and alef-maqsura, ta-marbuta and ha get mixed up by models and people.
    assert apply_arabic_terms("ابديت") == apply_arabic_terms("أبديت") == "update"
    assert apply_arabic_terms("كلاينت") == apply_arabic_terms("كلينت") == "client"


def test_unlisted_words_are_untouched():
    text = "ممكن تبعتلي الملف على الواتساب النهاردة"
    assert apply_arabic_terms(text) == text


def test_real_arabic_words_are_never_swapped():
    text = "ابي راح الشغل"  # "ابي" (my father) must not become "app"
    assert apply_arabic_terms(text) == text


def test_text_without_arabic_is_returned_as_is():
    assert apply_arabic_terms("the meeting is at noon") == "the meeting is at noon"
    assert apply_arabic_terms("") == ""
