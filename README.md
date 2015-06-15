[![Build Status](https://travis-ci.org/swistakm/solrq.svg?branch=master)](https://travis-ci.org/swistakm/solrq)
[![Coverage Status](https://coveralls.io/repos/swistakm/solrq/badge.svg)](https://coveralls.io/r/swistakm/solrq)
[![Documentation Status](https://readthedocs.org/projects/solrq/badge/?version=latest)](https://readthedocs.org/projects/solrq/?badge=latest)

# solrq
`solr` is a Python Solr query utility. It helps making query strings for Solr
and also helps with escaping reserved characters.

    pip install solrq
    
And you're ready to go!

# usage

Everything in `solrq` is about `Q()` object. Drop into python repl and just
feed it with bunch of field and search terms to see how it works:

    >>> from solrq import Q
    >>> # note: all terms in single Q object are implicitely joined with 'AND'
    >>> query = Q(type="animal", species="dog")
    >>> query
    <Q: type:animal AND species:dog>
    
    >>> # ohh, forgot about cats?
    >>> query | Q(type="animal", species="cat")
    <Q: (type:animal AND species:dog) OR (type:animal AND species:cat)>
    
    >>># more a cat lover? Let's give them a boost boost
    >>> Q(type="animal") & (Q(species="cat")^2 | Q(species="dog"))
    <Q: type:animal AND ((species:cat^2) OR species:dog)>


But what to do with this `Q`? Simply pass it to your Solr library of choice, 
like [pysolr](https://github.com/toastdriven/pysolr) or 
[mysolr](https://github.com/RedTuna/mysolr). Most of python Solr libraries
expect simple string as a query parameter and do not bother with escaping
of reserved characters so you must take care of that by yourself. This is why
`solrq` integrates so easily. Here is an example how you can use it with 
[pysolr](https://github.com/toastdriven/pysolr):

    from solrq import Q
    import pysolr
    
    solr = Solr("<your solr url>")
    
    # simply using Q object
    solr.search(Q(text="easy as f***"))

    # or explicitely making it string
    solr.search(str(Q(text="easy as f***")))
    
    
## quick reference

Full reference can be found in [API reference documentation page](http://solrq.readthedocs.org/en/latest/api-reference.html) 
but here is a short reference.

### boosting queries

Use python `^` operator:

    >>> Q(text='cat') ^ 2
    <Q: text:cat^2>


### AND queries

Use python `&` operator:

    >>> Q(text='cat') & Q(text='dog')
    <Q: text:cat AND text:dog>

### OR queries

Use python `|` operator:

    >>> Q(text='cat') | Q(text='dog')
    <Q: text:cat AND text:dog>
    

### NOT queries

Use python `~` operator:

    >>> ~ Q(text='cat')
    <Q: !text:cat>
    
### ranges:

Use `solrq.Range` wrapper:

    >>> from solrq import Range
    >>> Q(age=Range(18, 25))
    <Q: age:[18 TO 25]>


### proximity searches

Use `solrq.Proximity` wrapper:

    >>> from solrq import Proximity
    >>> Q(age=Proximity("cat dogs", 5))
    <Q: age:"cat\ dogs"~5>

### safe strings

All raw string values are treated as unsafe by default and will be escaped to 
ensure that final query string will not be broken by some rougue search value.
This of course can be disabled if you know what you're doing using
`Value` wrapper:

    >>> from solrq import Q, Value
    >>> Q(type='foo bar[]')
    <Q: type:foo\ bar\[\]>
    >>> Q(type=Value('foo bar[]', safe=True))
    <Q: type:foo bar[]>
    
    
### timedeltas, datetimes

Simply as:

    >>> from datetime import datetime, timedelta
    >>> Q(date=datetime(1970, 1, 1))
    <Q: date:"1970-01-01T00:00:00">
    >>> # note that timedeltas has any sense mostly with ranges
    >>> Q(delta=timedelta(days=1))
    <Q: delta:NOW+1DAYS+0SECONDS+0MILLISECONDS>
    
### field wildcard

If you need to use wildcards in field names just use dict and unpack it inside
of `Q()` instead of using keyword arguments:

    >>> Q(**{"*_t": "text_to_search"})
    <Q: *_t:text_to_search>


# contributing

Any contribution is welcome. Issues, suggestions, pull requests - whatever. 
There are no strict contribution guidelines beyond PEP-8 and sanity. 
Code style is checked with flakes8 and any PR that has failed build
will not be merged.

One thing: if you submit a PR please do not rebase it later unless you
are asked for that explicitely. Reviewing pull requests that suddenly had 
their history rewritten just drives me crazy.

# testing

Tests are run using tox. Simply install it and run:

    pip install tox
    tox
    
And that's all.

