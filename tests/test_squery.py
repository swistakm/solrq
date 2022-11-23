# -*- coding: utf-8 -*-
import pytest
from datetime import datetime, timedelta
import pytz

from solrq import (
    Q, QOperator, Value, Range, Proximity, ANY, SET
)


def test_query_simple():
    query = Q(foo="bar")
    assert str(query) == query.compile() == "foo:bar"


def test_query_and_implicit():
    query = Q(foo="bar", bar="foo")
    assert str(query) == query.compile() in (
        # note: in implicit operators we do not have control
        #   over item order
        "foo:bar AND bar:foo",
        "bar:foo AND foo:bar"
    )


def test_query_and_explitic():
    query = Q(foo="bar") & Q(bar="foo")
    assert str(query) == query.compile() == "foo:bar AND bar:foo"


def test_query_or_explitic():
    query = Q(foo="bar") | Q(bar="foo")
    assert str(query) == query.compile() == "foo:bar OR bar:foo"


def test_query_or_semi_implicit():
    query = Q(foo="bar", bar="foo", op=QOperator.or_)
    assert str(query) == query.compile() in (
        # note: in implicit operators we do not have control
        #   over item order
        "foo:bar OR bar:foo",
        "bar:foo OR foo:bar"
    )


def test_query_boost():
    query = Q(foo="bar") ^ 2
    assert str(query) == query.compile() == "foo:bar^2"

    query = Q(foo="bar") ^ 2.0
    assert str(query) == query.compile() == "foo:bar^2.0"

    # using bools with boosted terms
    query = Q(foo="bar") ^ 3 | Q(bar="baz") ^ 4
    assert str(query) == query.compile() == "(foo:bar^3) OR (bar:baz^4)"

    # boosting logical expression
    query = (Q(foo="bar") | Q(bar="baz")) ^ 3
    assert str(query) == query.compile() == "(foo:bar OR bar:baz)^3"

    # more complicated example, note: extra parenthesis will be added
    query = (Q(a="b") & Q(c="d")) ^ 1 | Q(e="f") ^ 2
    assert str(query) == query.compile() == "((a:b AND c:d)^1) OR (e:f^2)"


def test_constant_score():
    query = Q(foo="bar").constant_score(2)
    assert str(query) == query.compile() == "foo:bar^=2"

    query = Q(foo="bar").constant_score(2.0)
    assert str(query) == query.compile() == "foo:bar^=2.0"

    # using bools with constant score
    query = Q(foo="bar").constant_score(3) | Q(bar="baz").constant_score(4)
    assert str(query) == query.compile() == "(foo:bar^=3) OR (bar:baz^=4)"

    # constant score on logical expression
    query = (Q(foo="bar") | Q(bar="baz")).constant_score(3)
    assert str(query) == query.compile() == "(foo:bar OR bar:baz)^=3"

    # more complicated example, note: extra parenthesis will be added
    query = (Q(a="b") & Q(c="d")).constant_score(1) | Q(e="f").constant_score(2)  # noqa
    assert str(query) == query.compile() == "((a:b AND c:d)^=1) OR (e:f^=2)"


def test_query_not_simple():
    query = ~Q(foo="bar")
    assert str(query) == query.compile() == "!foo:bar"


def test_query_not_and_explicit():
    query = ~(Q(foo="bar") & Q(bar="foo"))
    assert str(query) == query.compile() == "!(foo:bar AND bar:foo)"


def test_usage_with_wildcards():
    query = Q(**{"*_t": "text"})
    assert str(query) == query.compile() == "*_t:text"


def test_query_invalid_initialization():
    with pytest.raises(ValueError):
        Q(children=[Q()], text="*")


def test_qoperator_invalid_invert_call():
    with pytest.raises(ValueError):
        QOperator.not_([Q(), Q()])


def test_operator_invalid_boost_call():
    with pytest.raises(ValueError):
        QOperator.boost([Q(), Q()], 1)

    with pytest.raises(TypeError):
        QOperator.boost([Q()], object())


def test_operator_invalid_constant_score_call():
    with pytest.raises(ValueError):
        QOperator.constant_score([Q(), Q()], 1)

    with pytest.raises(TypeError):
        QOperator.constant_score([Q()], object())


def test_value():
    assert str(Value('foo bar')) == 'foo\\ bar'
    assert str(Value('"foo bar"')) == '\\"foo\\ bar\\"'
    # note: this is how we wrap with quotes
    assert str(Value('"foo bar"', safe=True), ) == '"foo bar"'


def test_value_nonlocalized_datetimes():
    dt = datetime.now()
    assert str(Value(dt)) == '"{dt}Z"'.format(dt=dt.isoformat())


def test_value_localized_datetimes():
    dt = datetime.now()
    dt = dt.replace(tzinfo=pytz.timezone('Europe/Warsaw'))

    assert str(Value(dt)) == '"{dt}Z"'.format(
        dt=dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
    )


def test_value_timedelta():
    # positive deltas
    assert str(
        Value(timedelta(days=1, minutes=1, milliseconds=3))
    ) == "NOW+1DAYS+60SECONDS+3MILLISECONDS"

    # negative deltas
    assert str(
        Value(-timedelta(days=1))
    ) == "NOW-1DAYS+0SECONDS+0MILLISECONDS"

    # note: if datetime is passed and marked with safe it will nor be escaped
    # neither translated to Solr Date Math Syntax
    td = timedelta(days=1)
    assert str(Value(td, safe=True)) == str(td)


def test_range():
    assert str(Range(ANY, ANY)) == "[* TO *]"
    assert str(Range("*", "*", safe=True)) == "[* TO *]"
    assert str(Range("*", "*", safe=False)) == "[\\* TO \\*]"

    td_to = timedelta(days=2, minutes=1)
    td_from = -timedelta(days=2, minutes=1)

    # note: this all representations are equivalent
    assert str(
        Range(td_from, td_to)
    ) == str(
        Range(Value(td_from), Value(td_to))
    ) == "[{from_} TO {to}]".format(from_=Value(td_from), to=Value(td_to))

    # note: if marked as safe then each range sub-element will force-marked
    # as safe
    assert str(
        Range(td_from, td_to, safe=True)
    ) == str(
        Range(Value(td_from, safe=True), Value(td_to, safe=True))
    ) == "[{from_} TO {to}]".format(from_=td_from, to=td_to)


def test_range_boundaries_unsupported():
    with pytest.raises(ValueError):
        Range(1, 2, boundaries='<>')

    with pytest.raises(ValueError):
        Range(1, 2, boundaries='anything')


def test_range_boundaries():
    assert str(Range(0, 1, boundaries='inclusive')) == '[0 TO 1]'
    assert str(Range(0, 1, boundaries='exclusive')) == '{0 TO 1}'

    assert str(Range(0, 1, boundaries='ee')) == '{0 TO 1}'
    assert str(Range(0, 1, boundaries='ii')) == '[0 TO 1]'
    assert str(Range(0, 1, boundaries='ei')) == '{0 TO 1]'
    assert str(Range(0, 1, boundaries='ie')) == '[0 TO 1}'

    assert str(Range(0, 1, boundaries='{}')) == '{0 TO 1}'
    assert str(Range(0, 1, boundaries='[]')) == '[0 TO 1]'
    assert str(Range(0, 1, boundaries='{]')) == '{0 TO 1]'
    assert str(Range(0, 1, boundaries='[}')) == '[0 TO 1}'


def test_special():
    assert str(SET) == '[* TO *]'
    assert str(ANY) == '*'


def test_proximity():
    # note: boosting a string returns escaped space
    assert str(Proximity("foo bar", 12)) == '"foo\\ bar"~12'
    # ... but not if marked as safe
    assert str(Proximity("foo bar", 12, safe=True)) == '"foo bar"~12'

    # note: only marking safe on all stages ensures it will not be escaped
    assert str(
        Proximity(Value("foo bar", safe=True), 12, safe=True)
    ) == '"foo bar"~12'


def test_can_escape_special_characters():
    assert str(Q(foo="\\")) == "foo:\\\\"


def test_reprs():
    assert repr(Q(foo="bar"))
    assert repr(Value("foobar"))
