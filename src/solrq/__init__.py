# -*- coding: utf-8 -*-
VERSION = (0, 0, 3)  # PEP 386  # noqa
__version__ = ".".join([str(x) for x in VERSION])  # noqa

import re
from datetime import datetime, timedelta
from functools import partial


class Value(object):
    """
    Wrapper around any value that enables handling of escaping and further
    extensions query value translations.

    By default escapes all restricted characters so query can not be easily
    broken with unsafe strings. Also it recognizes ``timedelta`` and
    ``datetime`` objects so they can be represented in format that Solr can
    recognize (useful with ranges, see: `Range`)

    Args:
        raw (object): raw value object. Must be string, datetime, timedelta
                      or have ``__str__`` method defined.

        safe (bool): set to True to turn off character escaping

    Examples:

        In most cases you will pass string:

            >>> Value("foo bar")
            <Value: foo\\ bar>

        But it can be anything that has ``__str__`` method:

            >>> Value(1)
            <Value: 1>
            >>> Value(timedelta(days=1))
            <Value: NOW+1DAYS+0SECONDS+0MILLISECONDS>
            >>> Value(Value("foo"))
            <Value: foo>

        To get final query string just make it ``str``:

            >>> str(Value("foo bar"))
            'foo\\\\ bar'

        Note that raw strings are not safe by default:

            >>> Value('foo [] bar')
            <Value: foo\ \[\]\ bar>
            >>> Value("foo [] bar", safe=True)
            <Value: foo [] bar>

    """
    # note: since we escape spaces there is no need to escape AND, OR, NOT
    ESCAPE_RE = re.compile(r'(?<!\\)(?P<char>[ &|+\-!(){}[\]*^"~?:])')
    TIMEDELTA_FORMAT = "NOW{days:+d}DAYS{secs:+d}SECONDS{mills:+d}MILLISECONDS"

    def __init__(self, raw, safe=False):
        """
        Initialize Value object and if ``datetime`` or ``timedelta`` is
        passed as ``raw`` then immediately convert it to value that can be
        parsed by Solr.
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
        """
        Escape given string using ``Value.ESCAPE_RE`` expression.

        Args:
            string (str): string to escape
        """
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
    ``[<from> TO <to>]`` syntax with respect to restricted character esaping.

    Args:

        from_ (object): start of range, same as parameter ``raw`` in
            :class:`Value`.

        to (object): end of range, same as parameter ``raw`` in :class:`Value`.

    Examples:


        Simpliest range that matches all documents with some field set:

            >>> Range('*', '*', safe=True)
            <Range: [* TO *]>

        Note that there are shortucts already provided:

            >>> Range(ANY, ANY)
            <Range: [* TO *]>
            >>> SET
            <Range: [* TO *]>

        Other data types:

            >>> Range(0, 20)
            <Range: [0 TO 20]>
            >>> Range(timedelta(days=2), timedelta())
            <Range: [NOW+2DAYS+0SECONDS+0MILLISECONDS TO NOW]>

    Note:

        We could treat any iterables always as ranges when initializing
        :class:`Q` objects but "explicit is better than implicit" and also
        this would require to handle value representation there and we don't
        want to do that.

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

    Args:

        raw (str): string of words for proximity search

    Examples:

        >>> Proximity('foo bar', 4)
        <Proximity: "foo\ bar"~4>
        >>> Proximity('foo bar', 4, True)
        <Proximity: "foo bar"~4>

    Note:

        :class:`Proximity` will in fact accept any type as raw value that has
        ``__str__`` method defined so it is developer's responsibility to
        make sure that ``raw`` has a reasonable value.

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

        Args:

            qs_list (iterable): iterable of "compiled" query strings

        Returns:

            str: query strings joined with Solr `AND` operator as single string
        """
        return " AND ".join(qs_list)

    @classmethod
    def or_(cls, qs_list):
        """
        Perform 'or' operator routine

        Args:

            qs_list (iterable): iterable of "compiled" query strings

         Returns:

            str: query strings joined with Solr `OR` operator as single string
        """

        return " OR ".join(qs_list)

    @classmethod
    def not_(cls, qs_list):
        """
        Perform 'not' operator routine

        Args:

            qs_list (iterable): single item iterable of "compiled" query
                strings

        Returns:

           str: string with containing Solr ``!`` operator followed by query
               string

        Note:

            ``qs_list`` must be a list despite 'not' operator accepts only
            single query string here, to avoid more complexity in :class:`Q`
            objects
            initialization.
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

        Args:

            qs_list (iterable): single element list with compiled query string

            factor (float or int): boost factor

        Returns:

            str: compiled query string followed with '~' and boost factor


        Note:
            this operator routine is not intended to be directly used as
            :class:`Q` object argument but rather as a component for actual
            operator e.g:

                >>> from functools import partial
                >>> Q(children=[Q(a='b')], op=partial(QOperator.boost, factor=2))
                <Q: a:b^2>

        """  # noqa
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

    Args:

        children (iterable): iterable of children Q objects. **Note**: can't
            be used with kwargs

        op (callable): operator to join query parts

        kwargs (dict): list of query parts. Note: can't be used with children

    Examples:

        >>> Q(foo="bar")
        <Q: foo:bar>
        >>> str(Q(foo="bar"))
        'foo:bar'

        >>> Q(text="Skyrim")
        <Q: text:Skyrim>

        >>> Q(language="EN", text="Skyrim") # doctest: +ELLIPSIS
        <Q: ...>

        >>> ~(Q(language="EN", text="cat") | Q(language="PL", text="dog"))
        <Q: !((... AND ...) OR (... AND ...))>


    Note:

        it is possible to specify query params that are not valid python
        argument names using dictionary unpacking e.g.:

            >>> Q(**{"*_t": "text_to_search"})
            <Q: *_t:text_to_search>
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
        Initialize Q object using iterable of children or query
        params specified as keyword arguments.
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
        Build complex query using Solr ``AND`` operator.

        Args:

            other: right-hand operand

        Returns:

            Q: object representing Solr ``AND`` operator query

        Examples:

            >>> Q(type="animal") & Q(name="cat")
            <Q: type:animal AND name:cat>
        """
        return Q(children=[self, other], op=QOperator.and_)

    def __or__(self, other):
        """
        Build complex query using Solr ``OR`` operator.

        Args:

            other: right-hand operand

        Returns:

            Q: object representing Solr ``OR`` operator query

        Examples:

            >>> Q(type="animal") | Q(name="cat")
            <Q: type:animal OR name:cat>

        """
        return Q(children=[self, other], op=QOperator.or_)

    def __invert__(self):
        """
        Build complex query using Solr ``!`` operator.

        Returns:

            Q: object representing Solr ``!`` operator query

        Examples:

            >>> ~Q(type="animal")
            <Q: !type:animal>

        Note:

            We use here a ``~`` operator because it seems to fit best
            semanticaly to boolean 'not' operation. Despite Solr uses same
            character proximity searches (``~``) there is no place for
            confusion because ``__invert__`` in python accepts only one
            operand. For proximity searches there is a :class:`Proximity`
            class provided.

        """
        return Q(children=[self], op=QOperator.not_)

    def __xor__(self, other):
        """
        Build complex query using Solr boost operator.

        Args:

            other (float or int): boost value

        Returns:

            Q: object representing Solr query boosted by a given factor

        Examples:

            >>> Q(type="animal") ^ 2
            <Q: type:animal^2>

        """

        return Q(
            children=[self],
            op=partial(QOperator.boost, factor=other)
        )

    def compile(self, extra_parenthesis=False):
        """
        Compile :class:`Q` object into query string

        Args:

            extra_parenthesis (bool): add extra parenthesis to children query.

        Returns:

            str: compiled query string

        Examples:

            >>> (Q(type="animal") & Q(name="cat")).compile()
            'type:animal AND name:cat'
            >>> (Q(type="animal") & Q(name="cat")).compile(True)
            '(type:animal AND name:cat)'
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
        """
        String representation of :class:`Q` object (See :func:`Q.compile`)

        Returns:

            str: compiled query string


        """
        return self.compile()

    def __repr__(self):
        return "<{name}: {repr}>".format(
            name=self.__class__.__name__,
            repr=str(self),
        )
