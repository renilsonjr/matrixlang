import sys
from decimal import Decimal

import pytest

from matrixlang.values import (
    BadKey,
    check_key,
    is_bool,
    is_str,
    to_display,
    type_name,
)


def test_string_predicate():
    assert is_str("Neo") is True
    assert is_str(7) is False
    assert is_str(True) is False


def test_type_names_are_the_language_s_words():
    assert type_name(Decimal(7)) == "number"
    assert type_name(True) == "boolean"
    assert type_name("Neo") == "string"


def test_display_prints_strings_without_quotes():
    assert to_display("wake up") == "wake up"


def test_display_prints_booleans_in_the_language_s_spelling():
    # Python renders these "True"/"False"; MatrixLang spells them lowercase.
    assert to_display(True) == "true"
    assert to_display(False) == "false"


def test_display_prints_numbers():
    assert to_display(Decimal(0)) == "0"
    assert to_display(Decimal(-7)) == "-7"


def test_a_list_is_recognised_by_identity_of_type_not_isinstance():
    from matrixlang.values import is_list

    assert is_list([]) is True
    assert is_list([1, 2]) is True
    assert is_list("no") is False
    assert is_list(1) is False


def test_a_list_names_itself_list():
    from matrixlang.values import type_name

    assert type_name([1]) == "list"


def test_a_list_displays_with_brackets():
    from matrixlang.values import to_display

    assert to_display([]) == "[]"
    assert to_display([1, 2]) == "[1, 2]"
    assert to_display([True, False]) == "[true, false]"


def test_strings_are_quoted_inside_a_list_but_not_outside_one():
    # Bare `trace "hi"` prints hi. Inside a list, without quotes there is
    # no way to tell a string from a name and a list of strings becomes
    # unreadable, so the inconsistency is deliberate.
    from matrixlang.values import to_display

    assert to_display("hi") == "hi"
    assert to_display(["hi"]) == '["hi"]'
    assert to_display(["a", 1]) == '["a", 1]'


def test_a_quote_inside_a_displayed_string_is_escaped():
    from matrixlang.values import to_display

    assert to_display(['say "hi"']) == '["say \\"hi\\""]'


def test_nested_lists_display():
    from matrixlang.values import to_display

    assert to_display([[1], [2, 3]]) == "[[1], [2, 3]]"


def test_an_agent_inside_a_list_displays_by_name():
    from matrixlang.values import Function, to_display

    agent = Function("fib", ["n"], None, None)
    assert to_display([agent]) == "[<agent fib>]"


def test_displaying_a_cyclic_list_raises_a_named_error_not_a_recursion_error():
    # Measured before the design was written: the naive recursive
    # to_display raises RecursionError, which the interpreter converts to
    # "expression is nested too deeply" — a false statement about a
    # one-element list. A named exception is what lets the interpreter
    # report the truth.
    from matrixlang.values import CyclicValue, to_display

    xs = [1]
    xs[0] = xs
    with pytest.raises(CyclicValue):
        to_display(xs)


def test_displaying_a_mutual_cycle_also_raises_cyclic_value():
    # The self-referential case above (xs[0] = xs) is the direct cycle.
    # This is the mutual one: a[0] is b and b[0] is a, so neither list
    # contains itself, but walking either from the top still revisits an
    # id already on the path. Task 7's review verified this behaves
    # correctly but noted it had no committed test -- pin it here rather
    # than let it recurse to a bare RecursionError.
    from matrixlang.values import CyclicValue, to_display

    a = [1]
    b = [2]
    a[0] = b
    b[0] = a
    with pytest.raises(CyclicValue):
        to_display(a)


def test_a_sibling_list_reused_twice_is_not_a_cycle():
    # The false-positive direction: the same list object appearing twice
    # as a SIBLING (not on the path from itself back to itself) must not
    # be mistaken for a cycle. `seen` in _display is threaded per-branch
    # as an immutable frozenset, so one sibling's traversal can't poison
    # the other's -- getting this wrong would make ordinary shared lists
    # undisplayable.
    from matrixlang.values import to_display

    xs = [1]
    assert to_display([xs, xs]) == "[[1], [1]]"


# --- The rule the top-level guard could not reach ------------------------


def test_a_bool_never_equals_an_int_at_any_depth():
    # THE test for this task. The old code guarded operand types with
    # type_name and then handed off to Python's ==, where 1 == True. The
    # guard held exactly at the surface: [1] == [true] returned True.
    from matrixlang.values import Incomparable, equal

    for left, right in [
        (1, True),
        ([1], [True]),
        ([0], [False]),
        ([[1]], [[True]]),
        ([1, [2]], [1, [True]]),
    ]:
        with pytest.raises(Incomparable):
            equal(left, right)


def test_incomparable_carries_both_type_names():
    from matrixlang.values import Incomparable, equal

    with pytest.raises(Incomparable) as caught:
        equal([Decimal(1)], [True])
    assert caught.value.left == "number"
    assert caught.value.right == "boolean"


def test_lists_compare_structurally():
    from matrixlang.values import equal

    assert equal([1, 2], [1, 2]) is True
    assert equal([], []) is True
    assert equal([[1], [2]], [[1], [2]]) is True


def test_lists_of_different_contents_or_length_are_not_equal():
    from matrixlang.values import equal

    assert equal([1, 2], [1, 3]) is False
    assert equal([1], [1, 2]) is False
    assert equal([1, 2], [1]) is False


def test_scalars_still_compare_by_value():
    from matrixlang.values import equal

    assert equal(1, 1) is True
    assert equal("a", "a") is True
    assert equal(True, True) is True
    assert equal(1, 2) is False


def test_comparing_across_types_is_incomparable():
    from matrixlang.values import Incomparable, equal

    with pytest.raises(Incomparable):
        equal("3", 3)
    with pytest.raises(Incomparable):
        equal([1], 1)


def test_agents_compare_by_identity_inside_a_list():
    from matrixlang.values import Function, equal

    a = Function("f", [], None, None)
    b = Function("f", [], None, None)
    assert equal([a], [a]) is True
    assert equal([a], [b]) is False


# --- Cycles --------------------------------------------------------------


def test_cyclic_lists_compare_without_blowing_the_stack():
    # Measured: Python's per-element identity shortcut saves `a == a` but
    # NOT two mutually referential lists, which raise RecursionError.
    from matrixlang.values import equal

    b = [None]
    c = [None]
    b[0] = c
    c[0] = b

    d = [None]
    e = [None]
    d[0] = d
    e[0] = e

    a = [1]
    a[0] = a

    assert equal(b, c) is True
    assert equal(d, e) is True
    assert equal(a, a) is True


def test_a_shared_sublist_is_walked_correctly_when_the_same_pair_recurs():
    # `seen` is a memo of pairs already proven equal within this call, not
    # a path-scoped "currently visiting" set -- nothing is removed on the
    # way back up. That's sound because a `False` result or an
    # Incomparable exception propagates straight to the top of the
    # outermost `equal()` call: a pair is only ever memoized after really
    # being proven equal, so consulting the memo again returns exactly
    # what recomputing it would. Exercise the case that motivates keeping
    # entries around: the same object pair reached twice in one call,
    # both when it is equal and when it is not.
    from matrixlang.values import equal

    same_left = [1, 2]
    same_right = [1, 2]
    assert equal([same_left, same_left], [same_right, same_right]) is True

    other_right = [1, 9]
    assert equal([same_left, same_left], [other_right, other_right]) is False


def test_a_cyclic_pair_terminates_by_assuming_equality_on_re_entry():
    # Re-entering a pair still being compared further up the stack
    # returns True -- the standard coinductive treatment of cycles, and
    # the reason equal() terminates on cyclic input at all instead of
    # recursing forever.
    from matrixlang.values import equal

    a = [None]
    a[0] = a
    b = [None]
    b[0] = b
    assert equal(a, b) is True


def test_a_number_too_long_to_render_raises_a_named_signal():
    # Was `10 ** (...)`, a bare Python int. `is_number` is `type(value)
    # is Decimal` exactly, so a bare int never reaches the number branch
    # in `_display` at all -- it falls through to the generic `str()`
    # fallback at the bottom, which raises its own ValueError-turned-
    # TooManyDigits *unconditionally* past CPython's cap. That fallback
    # path made this test pass even with the real guard -- the `elif
    # abs(value.adjusted()) >= sys.get_int_max_str_digits()` check a few
    # lines up in `_display`'s number branch -- deleted outright, since
    # nothing here ever reached it. A `Decimal` this long exercises the
    # actual guard, and it is the ONLY thing standing here: CPython
    # refuses `str(int)` past sys.get_int_max_str_digits(), but
    # `format(Decimal, "f")` does NOT -- it hands back 5001 characters for
    # `Decimal("1" + "0" * 5000)` and raises nothing. There is no
    # ValueError underneath this test to catch what the guard misses.
    # (The comment here used to claim there was. It was written when this
    # path still went through str(int), and shipped uncorrected.)
    #
    # So the guard is not a second line of defence, it IS the defence:
    # delete it and a program prints a five-thousand-character number
    # instead of a diagnostic. TooManyDigits is named for the same reason
    # as CyclicValue: values.py knows the value cannot be rendered, the
    # interpreter knows where it was written.
    from decimal import Decimal

    from matrixlang.values import TooManyDigits, to_display

    with pytest.raises(TooManyDigits) as caught:
        to_display(Decimal("9" * (sys.get_int_max_str_digits() + 1)))
    assert caught.value.limit == sys.get_int_max_str_digits()


def test_a_number_just_under_the_ceiling_still_renders():
    # The boundary in the other direction. A guard that reported every
    # long number as unrenderable would pass the test above and break
    # arithmetic nobody thinks of as extreme. `Decimal`, not a bare
    # Python int, for the same reason as the test above -- a bare int
    # never reaches this guard at all, so it cannot pin the boundary of
    # something it never exercises.
    from decimal import Decimal

    from matrixlang.values import to_display

    limit = sys.get_int_max_str_digits()
    rendered = to_display(Decimal("9" * (limit - 1)))
    assert len(rendered) == limit - 1


def test_a_dictionary_names_itself_dictionary():
    assert type_name({}) == "dictionary"


def test_a_dictionary_displays_with_quoted_string_keys():
    assert to_display({"a": 1, "b": "x"}) == '{"a": 1, "b": "x"}'


def test_a_dictionary_displays_number_keys_unquoted():
    assert to_display({Decimal(1): "x"}) == '{1: "x"}'


def test_an_empty_dictionary_displays_as_empty_braces():
    assert to_display({}) == "{}"


def test_a_self_containing_dictionary_raises_cyclic():
    from matrixlang.values import CyclicValue

    d = {}
    d["self"] = d
    with pytest.raises(CyclicValue):
        to_display(d)


def test_dictionary_equality_ignores_order():
    from matrixlang.values import equal

    assert equal({"a": 1, "b": 2}, {"b": 2, "a": 1})


def test_dictionary_equality_does_not_use_pythons_equals():
    # Python says {"a": 1} == {"a": True}. The language must not: 1 and
    # true are different types, and comparing them is an error at every
    # depth. This is the list bug -- [1] == [true] -- one level down.
    from matrixlang.values import Incomparable, equal

    with pytest.raises(Incomparable):
        equal({"a": 1}, {"a": True})


def test_dictionaries_with_different_keys_are_unequal():
    from matrixlang.values import equal

    assert not equal({"a": 1}, {"b": 1})


def test_dictionaries_of_different_size_are_unequal():
    from matrixlang.values import equal

    assert not equal({"a": 1}, {"a": 1, "b": 2})


def test_two_mutually_referential_dictionaries_compare_without_recursing_forever():
    from matrixlang.values import equal

    a, b = {}, {}
    a["x"], b["x"] = b, a
    assert equal(a, b)


def test_a_string_key_is_accepted():
    check_key("a")


def test_a_number_key_is_accepted():
    from decimal import Decimal

    check_key(Decimal(1))


def test_a_boolean_key_is_rejected():
    # Not squeamishness. Python hashes True and 1 identically, so a
    # dictionary holding both would silently collapse to one entry --
    # two keys written, one given, and no diagnostic anywhere.
    with pytest.raises(BadKey):
        check_key(True)


def test_a_list_key_is_rejected():
    with pytest.raises(BadKey):
        check_key([1])


def test_a_dictionary_key_is_rejected():
    with pytest.raises(BadKey):
        check_key({})


def test_a_number_is_a_decimal():
    from decimal import Decimal

    from matrixlang.values import is_number, is_whole

    assert is_number(Decimal("1.5"))
    assert is_number(Decimal(3))
    assert not is_number(3)
    assert not is_number("3")
    assert not is_number(True)


def test_whole_means_nothing_after_the_point():
    from decimal import Decimal

    from matrixlang.values import is_whole

    assert is_whole(Decimal(3))
    assert is_whole(Decimal("3.0"))
    assert not is_whole(Decimal("3.5"))
    assert not is_whole("3")


def test_the_type_name_is_number():
    from decimal import Decimal

    from matrixlang.values import type_name

    assert type_name(Decimal(3)) == "number"
    assert type_name(Decimal("3.5")) == "number"


def test_a_boolean_is_still_not_a_number():
    # The bool/int separation that check_key depends on must survive the
    # move to Decimal. type(True) is bool, never Decimal, so it holds by
    # construction -- but it is load-bearing enough to pin.
    from matrixlang.values import is_number, type_name

    assert not is_number(True)
    assert type_name(True) == "boolean"


def test_whole_numbers_display_without_a_point():
    from decimal import Decimal

    from matrixlang.values import to_display

    assert to_display(Decimal(3)) == "3"
    assert to_display(Decimal("3.0")) == "3.0"
    assert to_display(Decimal("2.50")) == "2.50"


def test_display_never_uses_scientific_notation():
    # str(Decimal("1e3")) is "1E+3". A reader must never see that.
    from decimal import Decimal

    from matrixlang.values import to_display

    assert to_display(Decimal("1e3")) == "1000"
    assert to_display(Decimal("1e-3")) == "0.001"


def test_arithmetic_is_exact_where_it_can_be():
    from decimal import Decimal

    from matrixlang.values import EXACT

    assert EXACT.add(Decimal("0.1"), Decimal("0.2")) == Decimal("0.3")
    assert EXACT.multiply(Decimal("9" * 40), Decimal(2)) == Decimal(
        "1" + "9" * 39 + "8"
    )


def test_division_rounds_where_it_must():
    from decimal import Decimal

    from matrixlang.values import DIVISION

    assert DIVISION.divide(Decimal(1), Decimal(3)) == Decimal(
        "0.3333333333333333333333333333"
    )
    assert DIVISION.divide(Decimal(7), Decimal(2)) == Decimal("3.5")


def test_repeated_squaring_overflows_as_number_overflow():
    # decimal.Overflow is a bare ArithmeticError, not a MatrixLangError.
    # EXACT's precision (1000) pushes Emax to 999999, but repeated
    # squaring gets there well inside any step budget -- 10, squared 19
    # times, is already past it. NumberOverflow is what must come out
    # instead, from the context itself, since EXACT.multiply(...) is
    # called directly by later tasks with no call-site try/except of
    # their own.
    from decimal import Decimal

    from matrixlang.values import EXACT, NumberOverflow

    v = Decimal(10)
    with pytest.raises(NumberOverflow):
        for _ in range(30):
            v = EXACT.multiply(v, v)


def test_overflow_never_produces_an_infinite_decimal():
    # The trap stays ON: decimal.Overflow fires before an infinite result
    # is ever materialized. That matters because is_whole(Infinity) is
    # True (Infinity equals its own to_integral_value()) -- an Infinity
    # that leaked out of EXACT/DIVISION would become a usable index or a
    # usable `length`. Guarding by catching, rather than by clearing the
    # context's traps and inspecting the result afterward, is what keeps
    # that value from ever existing in the first place.
    from decimal import Decimal

    from matrixlang.values import EXACT, NumberOverflow

    v = Decimal(10)
    with pytest.raises(NumberOverflow):
        for _ in range(30):
            v = EXACT.multiply(v, v)
    assert v != Decimal("Infinity")


def test_division_can_also_overflow():
    from decimal import Decimal

    from matrixlang.values import DIVISION, NumberOverflow

    with pytest.raises(NumberOverflow):
        DIVISION.divide(Decimal("1E+999990"), Decimal("1E-999990"))


def test_addition_can_also_overflow():
    from decimal import Decimal

    from matrixlang.values import EXACT, NumberOverflow

    with pytest.raises(NumberOverflow):
        EXACT.add(Decimal("9E+999999"), Decimal("9E+999999"))


def test_a_zero_of_any_magnitude_displays_as_zero_not_too_many_digits():
    # adjusted() on a zero reports its EXPONENT, not its magnitude --
    # Decimal("0E-5000").adjusted() is -5000, past the digit cap, for a
    # value that is exactly zero. Reachable: repeated division underflows
    # to values like Decimal('0E-1000026').
    from decimal import Decimal

    from matrixlang.values import to_display

    assert to_display(Decimal("0E-5000")) == "0." + "0" * 5000
    assert to_display(Decimal(0)) == "0"


def test_negative_zero_displays_without_a_minus_sign():
    # Python's own `0 * -1` is `0`, not `-0`. EXACT.multiply(0, -1) is
    # Decimal("-0") -- if that reached display unchanged, a translated
    # `print(0 * -1)` would print "-0" on one side and "0" on the other,
    # a silent difference between the two runtimes.
    from decimal import Decimal

    from matrixlang.values import EXACT, to_display

    assert to_display(EXACT.multiply(Decimal(0), Decimal(-1))) == "0"
    assert to_display(Decimal("-0")) == "0"
    assert to_display(Decimal("-0.00")) == "0.00"


def test_a_decimal_too_long_to_render_still_raises_too_many_digits():
    # A value can be perfectly legal to EXACT (Emax is 999999, far above
    # the display cap) and still be too long to ever put on screen.
    # NumberOverflow and TooManyDigits are two independent checks at two
    # different times -- arithmetic not overflowing is no promise that
    # the result will still be displayable.
    from decimal import Decimal

    from matrixlang.values import TooManyDigits, to_display

    with pytest.raises(TooManyDigits) as caught:
        to_display(Decimal("1E+5000"))
    assert caught.value.limit == sys.get_int_max_str_digits()


def test_remainder_floor_agrees_with_python_across_a_random_spread():
    # The algorithm's own pin, below the interpreter. Python's `%` on ints
    # IS the rule remainder_floor implements, so the differential is the
    # specification -- exponents up to 60 digits on both sides, both signs
    # on both operands, and enough draws that any surviving sign or
    # boundary case shows up.
    import random
    from decimal import Decimal

    from matrixlang.values import remainder_floor

    rng = random.Random(20260824)
    for _ in range(2000):
        a = rng.randint(-(10 ** rng.randint(1, 60)), 10 ** rng.randint(1, 60))
        b = rng.choice([-1, 1]) * rng.randint(1, 10 ** rng.randint(1, 30))
        assert remainder_floor(Decimal(a), Decimal(b)) == Decimal(a % b)


@pytest.mark.parametrize("digits", [1001, 1025, 1999])
def test_remainder_floor_stays_exact_past_exacts_precision(digits):
    # The quotient here needs more than EXACT's 1000 significant digits.
    # Flooring a ROUNDED quotient rounded UP and returned -1 for a positive
    # divisor; asking Context.remainder for it in one step raises
    # decimal.InvalidOperation (DivisionImpossible). Both wrong answers are
    # pinned out here in one place.
    #
    # 1999 is the top of the exact range, not an arbitrary large number:
    # each remainder step rounds its own result to prec digits and leaves
    # about digits(left) - prec behind, so 2 * prec is where exactness
    # stops. Past it the answer rounds -- the same way EXACT.add already
    # rounds a 2000-digit operand -- but the SIGN still holds, which is
    # the next test.
    from decimal import Decimal

    from matrixlang.values import remainder_floor

    a = int("9" * digits)
    for dividend in (a, -a):
        for divisor in (2, -2, 7, -7):
            assert remainder_floor(
                Decimal(dividend), Decimal(divisor)
            ) == Decimal(dividend % divisor)


def test_remainder_floor_keeps_the_finer_of_the_two_scales():
    # Trailing zeros are significant in this language, and `%` must not
    # quietly normalize them away: 49.90 % 7 is 0.90, not 0.9.
    from decimal import Decimal

    from matrixlang.values import remainder_floor

    assert str(remainder_floor(Decimal("49.90"), Decimal(7))) == "0.90"
    assert str(remainder_floor(Decimal("7.5"), Decimal(-2))) == "-0.5"


@pytest.mark.parametrize("digits", [1025, 3000, 6000])
def test_remainder_floor_never_contradicts_the_divisors_sign(digits):
    # The binding rule, and the one that broke: `a - floor(a / b) * b`
    # cannot produce a negative remainder for a positive divisor. Past 2 *
    # EXACT.prec digits the exact answer is out of reach (see above), so
    # this pins the part that is NOT allowed to degrade with size. The sign
    # correction is unconditional, so this holds by shape rather than by
    # precision -- which is exactly what the old divide-then-floor spelling
    # could not claim.
    from decimal import Decimal

    from matrixlang.values import remainder_floor

    a = Decimal("9" * digits)
    for dividend in (a, -a):
        for divisor in (Decimal(2), Decimal(-2), Decimal("0.7"), Decimal("-0.7")):
            got = remainder_floor(dividend, divisor)
            assert got.is_zero() or (got < 0) == (divisor < 0)
            assert abs(got) <= abs(divisor)
