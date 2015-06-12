# -*- coding: utf-8 -*-
VERSION = (0, 0, 1)  # PEP 386  # noqa
__version__ = ".".join([str(x) for x in VERSION])  # noqa

import re
from datetime import datetime, timedelta
from functools import partial


class Value(object):
    """
    Wrapper around any value that enables handling of escaping and further
    extensions query value translations.

    By default escapes all restricted characters so query can not be easily
    breaken with unsafe strings. Also it recognizes `timedelta` and
    `datetime` objects so they can be represented in format that Solr can
    recognize (useful with ranges, see: `Range`)

    Example usage:

        >>> Value("foo bar")           # in most cases it will be str
        <Value: foo\\ bar>
        >>> Value(1)                   # but can be anything that has __str__
        <Value: 1>
        >>> Value(timedelta(days=1))   # like timedelta or  datetime
        <Value: NOW+2DAYS+0SECONDS+0MILLISECONDS>
        >>> str(Value("foo bar"))      # just make it str to get a query string
        'foo\ bar'
        >>> Value('foo [] bar')        # not safe by default
        <Value: foo\ \[\]\ bar>
        >>> Value("not [safe]", True)  # but escaping can be turned off
        <Value: not [safe]>

    """
    # note: since we escape spaces there is no need to escape AND, OR, NOT
    ESCAPE_RE = re.compile(r'(?<!\\)(?P<char>[ &|+\-!(){}[\]*^"~?:])')
    TIMEDELTA_FORMAT = "NOW{days:+d}DAYS{secs:+d}SECONDS{mills:+d}MILLISECONDS"

    def __init__(self, raw, safe=False):
        """
        Initialize Value object and if `datetime` or `timedelta` is passed
        as `raw` then immediately convert it to value that can be parsed by
        Solr.

        :param raw: raw value object. Must have __str__ method defined
        :param safe: set to True to turn off character escaping
        """
        if isinstance(raw, datetime) and not safe:
            # Note: solr speaks ISO, wrap it with quotes to avoid further
            # escaping
            self.raw = '"{dt}"'.format(dt=raw.isoformat())
            # since we translated value we can safely mark it safe
            self.safe = True
        elif isinstance(raw, timedelta) and not safe:
            # Make representation compatibile with Solr Date Math Syntax
            # Note: at first look this can look weird since it can produce
            # strings with mixed singn for negative deltas e.g:
            #
            #     >>> Value(-timedelta(days=2, hours=2))
            #     <Value: NOW-3DAYS+79200SECONDS+0MILLISECONDS>
            #
            #  but this is a valid representation and Solr can handle it
            self.raw = self.TIMEDELTA_FORMAT.format(
                days=raw.days,
                secs=raw.seconds,
                mills=int(raw.microseconds / 1000)
            ) if not raw == timedelta() else 'NOW'
            # since we translated value we can safely mark it safe
            self.safe = True
        else:
            self.raw = raw
            self.safe = safe

    @classmethod
    def _escape(cls, string):
        return cls.ESCAPE_RE.sub(r'\\\g<char>', string)

    def __str__(self):
        return str(self.raw) if self.safe else self._escape(str(self.raw))

    def __repr__(self):
        return "<{name}: {repr}>".format(
            name=self.__class__.__name__,
            repr=str(self),
        )


class Range(Value):
    """
    Wrapper around range values. Wraps two values with Solr's
    '[<from> TO <to>]' syntax with respect to restricted character esaping.

    Example usage:

        >>> Range('*', '*', safe=True)  # equiv: `Range(ANY, ANY)` or `SET`
        <Range: [* TO *]>
        >>> Range(0, 10)
        <Range: [0 TO 20]>
        >>> Range(timedelta(days=2), timedelta())
        <Range: [NOW+2DAYS+0SECONDS+0MILLISECONDS TO NOW]>


    Note: We could treat any iterables always as ranges when initializing Q
    objects but "explicit is better than implicit" and also this would require
    to handle value representation there and we don't want to do that.

    """
    def __init__(self, from_, to, safe=None):
        self.from_ = (
            from_ if isinstance(from_, Value) else Value(from_, safe or False)
        )
        self.to = (
            to if isinstance(to, Value) else Value(to, safe or False)
        )

        # override safe values if safe is specified
        if safe is not None:
            self.from_.safe = safe
            self.to.safe = safe

        super(Range, self).__init__(
            "[{from_} TO {to}]".format(from_=self.from_, to=self.to),
            # Note: parts will be safe'd or not so no need for further escaping
            True
        )


class Proximity(Value):
    """
    Wrapper for proximity searches.

    Example usage:

        >>> Proximity('foo bar', 4)        # 'foo' and 'bar' with distance of 4
        <Proximity: "foo\ bar"~4>
        >>> Proximity('foo bar', 4, True)  # without escaping
        <Proximity: "foo bar"~4>
    """
    def __init__(self, raw, distance, safe=False):
        self.distance = distance
        super(Proximity, self).__init__(raw, safe)

    def __str__(self):
        return '"{val}"~{distance:d}'.format(
            val=super(Proximity, self).__str__(),
            distance=self.distance
        )


ANY = Value("*", safe=True)
SET = Range(ANY, ANY)


class QOperator(object):
    """
    This class is a namespace for handling Q object operator routines
    """

    @classmethod
    def and_(cls, qs_list):
        """
        Perform 'and' operator routine

        :param qs_list: list of "compiled" query strings
        :return: query strings joined with Solr 'AND' operator as single
            string
        """
        return " AND ".join(qs_list)

    @classmethod
    def or_(cls, qs_list):
        """
        Perform 'or' operator routine

        :param qs_list: list of "compiled" query strings
        :return: query strings joined with Solr 'AND' operator as single
            string
        """

        return " OR ".join(qs_list)

    @classmethod
    def not_(cls, qs_list):
        """
        Perform 'not' operator routine

        Note: `qs_list` must be a list despite 'not' operator accepts only
        single query string here, to avoid more complexity in `Q` objects
        initialization.

        :param qs_list: single element list with compiled query string
        :return: Solr 'NOT' operator followed with given query string
        """
        if len(qs_list) != 1:
            raise ValueError(
                "<invert> operator can receive only single Q object as operand"
            )
        return "!{qs}".format(qs=qs_list[0])

    @classmethod
    def boost(cls, qs_list, factor):
        """
        Perform 'boost' operator routine

        Note: this operator routine is not intended to be directly used as
        `Q` object argument but rather as component for actual operator e.g:

            >>> from functools import partial
            >>> Q(children=[Q(a='b')], op=partial(QOperator.boost, factor=2))
            <Q: a:b^2>

        :param qs_list: single element list with compiled query string
        :param factor: boost factor
        :return: compiled query string followed with '~' and boost factor
        """
        if len(qs_list) != 1:
            raise ValueError(
                "<boost> operator can receive only single Q object"
            )

        if not isinstance(factor, (int, float)):
            raise TypeError(
                "boost factor must be either int or float"
            )

        return "{qs}^{factor}".format(qs=qs_list[0], factor=factor)


class Q(object):
    """
    Class for handling Solr queries in semantic way.

    Example usage:

        >>> Q(foo="bar")
        <Q: foo:bar>
        >>> str(Q(foo="bar"))
        'foo:bar'

        >>> q = Q(text="Skyrim")
        <Q: text:Skyrim>

        >>> q = Q(language="EN", text="Skyrim")
        <Q: language:EN AND text:Skyrim>

        >>> q = ~(Q(language="EN", text="cat") | Q(language="PL", text="dog"))
        <Q: !((language:EN AND text:cat) OR (language:PL AND text:dog))>


    Note: only little magic inside (tm)
    """
    _children = None
    _op = None

    def __init__(
            self,
            children=None,
            op=QOperator.and_,
            **kwargs
    ):
        """
        Initialize Q object using set (iterable) of children or query
        params specified as Q.

        Note: it is possible to specify query params that are not valid
        python parameter names using dictionary unpacking e.g.:

            >>> Q(**{"*_t": "text_to_search"})

        :param children: list of children Q objects. Note: can't be used
            with kwargs
        :param op: operator to join query parts
        :param kwargs: list of query parts. Note: can't be used with children
        :return:
        """
        if kwargs and children:
            raise ValueError(
                "{cls} object can be instantiated only with qeury tuple or"
                "iterable of children but not with both".format(
                    cls=self.__class__.__name__
                )
            )

        elif kwargs and len(kwargs) == 1:
            # the simpliest case: one term Q object
            self.field, self.query = kwargs.popitem()

            if not isinstance(self.query, Value):
                self.query = Value(self.query)

        elif kwargs:
            # if not then istantiate new Q object as children using
            # given parameter.
            # Note: this is a place when implicit AND happens
            self._children = [
                Q(**{term: qs}) for term, qs in kwargs.items()
            ]
            self._operator = op

        elif children:
            self._children = children
            self._operator = op

    def __and__(self, other):
        """
        Build complex query using Solr 'AND' operator.

        Example usage:

            >>> Q(type="animal") & Q(name="cat")
            <Q: type:animal AND name:cat>

        :param other: right operand
        :return: `Q` object representing Solr 'AND' operator
        """
        return Q(children=[self, other], op=QOperator.and_)

    def __or__(self, other):
        """
        Build complex query using Solr 'OR' operator.

        Example usage:

            >>> Q(type="animal") | Q(name="cat")
            <Q: type:animal OR name:cat>

        :param other: right operand
        :return: `Q` object representing Solr 'OR' operator
        """
        return Q(children=[self, other], op=QOperator.or_)

    def __invert__(self):
        """
        Build complex query using Solr '!1' operator.

        Example usage:

            >>> ~Q(type="animal")
            <Q: !type:animal>

        Note: we use here a '~' operator because it seems to fit best
        semanticaly to boolean 'not' operation. Despite Solr uses same
        character proximity searches ('~') there is no place for confusion
        because __invert__ in python accepts only one operand. For proximity
        searches there is a `Proximity` class provided.

        :return: `Q` object representing Solr 'NOT' operator
        """
        return Q(children=[self], op=QOperator.not_)

    def __xor__(self, other):
        """
        Build complex query using Solr boost operator.

        Example usage:

            >>> ~Q(type="animal")
            <Q: !type:animal>

        :return: `Q` object representing Solr query boosted by a given factor
        :param other: boost factor value
        :return:
        """

        return Q(
            children=[self],
            op=partial(QOperator.boost, factor=other)
        )

    def compile(self, extra_parenthesis=False):
        """
        Compile `Q` object into query string

        Example usage:

            >>> (Q(type="animal") & Q(name="cat")).compile()
            'type:animal AND name:cat'
            >>> (Q(type="animal") & Q(name="cat")).compile(True)
            '(type:animal AND name:cat)'

        :param extra_parenthesis: add extra parenthesis children children
          query.
        :return: compiled query string
        """
        if not self._children:
            query_string = "{field}:{qs}".format(
                field=self.field,
                qs=self.query
            )
        else:
            query_string = self._operator([
                child.compile(extra_parenthesis=True)
                for child
                in self._children
            ])

            if extra_parenthesis:
                query_string = "({qs})".format(qs=query_string)

        return query_string

    def __str__(self):
        return self.compile()

    def __repr__(self):
        return "<{name}: {repr}>".format(
            name=self.__class__.__name__,
            repr=str(self),
        )
