"""Parsing functions for Fluidinfo queries.

Fluidinfo has a simple query language that allows applications to search for
objects based on their tags' values.  The following kinds of queries are
possible:

 - Equality and Inequality: To find objects based on the numeric value of
     tags, e.g., C{tim/rating > 5}, or exact textual values, e.g.,
     C{geo/name = "Llandefalle"}.

 - Textual: To find objects based on text matching of their tag values, e.g.,
     C{sally/opinion matches "fantastic"}.

 - Presence: Use C{has} to request objects that have a given tag. For example,
     C{has sally/opinion}.

 - Set contents: A tag on an object can hold a set of strings.  For example, a
     tag called C{mary/product-reviews/keywords} might be on an object with a
     value of C{["cool", "kids", "adventure"]}.  The C{contains} operator can
     be used to select objects with a matching value.  The query
     C{mary/product-reviews/keywords contains "kids"} would match the object in
     this example.

 - Exclusion: You can exclude objects with the except keyword.  For example has
     C{nytimes.com/appeared except has james/seen}.  The except operator
     performs a set difference.

 - Logic: Query components can be combined with C{and} and C{or}.  For
     example, C{has sara/rating and tim/rating > 5}.

 - Grouping: Parentheses can be used to group query components.  For example,
     C{has sara/rating and (tim/rating > 5 or mike/rating > 7)}.
"""
from threading import currentThread

from fluiddb.application import getConfig
from fluiddb.exceptions import FeatureError
from fluiddb.query.grammar import QueryLexer, QueryParser, Node


__all__ = ["IllegalQueryError", "parseQuery"]


class IllegalQueryError(Exception):
    """Raised if a query contains an illegal expression."""


def parseQuery(query):
    """Parse a Fluidinfo query.

    This function is not thread-safe.  See L{getQueryLexer} and
    L{getQueryParser} for more details.

    @param query: A C{unicode} Fluidinfo query.
    @raise IllegalQueryError: Raised if the query contains illegal expressions.
    @raise QueryParseError: Raised if the query can't be parsed.
    @raise FeatureError: Raised if this function is invoked outside the main
        thread.
    @return: A L{Query} instance representing the parsed query.
    """
    parsedQuery = _parseQuery(query)
    for illegalQuery in getIllegalQueries():
        if parsedQuery.contains(illegalQuery):
            raise IllegalQueryError('Query contains an illegal expression.')

    return parsedQuery


def _parseQuery(query):
    """Parse a Fluidinfo query without doing illegal query checks.

    @param query: A C{unicode} Fluidinfo query.
    @raise QueryParseError: Raised if the query can't be parsed.
    @raise FeatureError: Raised if this function is invoked outside the main
        thread.
    @return: A L{Query} instance representing the parsed query.
    """
    lexer = getQueryLexer()
    parser = getQueryParser()
    return Query(query, parser.parse(query, lexer.lexer))


class Query(object):
    """A Fluidinfo query.

    @param text: A valid C{unicode} Fluidinfo query.
    @param rootNode: A L{Node} instance that represents the abstract syntax
        tree generated for C{text}.
    """

    def __init__(self, text, rootNode):
        self.text = text
        self.rootNode = rootNode

    def getPaths(self):
        """Get the L{Tag.path}s present in this query.

        @return: A C{set} of L{Tag.path}s in this query.
        """

        def traverse(node):
            paths = set()
            if node.left is not None:
                paths.update(traverse(node.left))
            if node.right is not None:
                paths.update(traverse(node.right))
            if node.kind not in (Node.AND, Node.OR, Node.EXCEPT,
                                 Node.PATH, Node.VALUE, Node.KEY):
                paths.add(node.left.value)
            return paths

        return traverse(self.rootNode)

    def contains(self, query):
        """Determine if C{query} is contained within this query.

        Note that this method only matches simple queries that represent a
        single expression.

        @param query: The L{Query} to match against this one.
        @raises FeatureError: Raised if C{query} is too complex to match.
        @return: C{True} if C{query} is present, otherwise C{False}.
        """
        if query.rootNode.left is not None:
            if (query.rootNode.left.left is not None or
                    query.rootNode.left.right is not None):
                raise FeatureError("Query is too complex to match.")
        if query.rootNode.right is not None:
            if (query.rootNode.right.left is not None or
                    query.rootNode.right.right is not None):
                raise FeatureError("Query is too complex to match.")

        def traverse(node):
            if node is None:
                return False
            elif (node == query.rootNode and
                  node.left == query.rootNode.left and
                  node.right == query.rootNode.right):
                return True
            else:
                return traverse(node.left) or traverse(node.right)

        return traverse(self.rootNode)


_parser = None


def getQueryParser():
    """Get a L{QueryParser} to parse Fluidinfo queries.

    The process of building a L{QueryParser} is quite expensive.  PLY
    generates parse tables and writes them to a file on disk.  As a result, a
    single parser instance is generated and cached in memory.  The same
    L{QueryParser} instance is returned each time this function is called.

    As a result, you must be especially careful about thread-safety.  The
    L{QueryParser} must only be used to parse one input at a time and never
    shared among threads.

    @raise FeatureError: Raised if this function is invoked outside the main
        thread.
    @return: The global L{QueryParser} instance.
    """
    if currentThread().getName() != 'MainThread':
        raise FeatureError(
            'A query parser may only be used in the main thread.')

    global _parser
    if _parser is None:
        lexer = getQueryLexer()
        parser = QueryParser(lexer.tokens)
        parser.build(module=parser, debug=False,
                     outputdir=getConfig().get('service', 'temp-path'))
        _parser = parser
        # Setup illegal queries to ensure we do it in a safe way and avoid
        # races.
        getIllegalQueries()
    return _parser


_lexer = None


def getQueryLexer():
    """Get a L{QueryLexer} to tokenize Fluidinfo queries.

    The same L{QueryLexer} instance is returned each time this function is
    called.  As a result, you must be especially careful about thread-safety.
    The L{QueryLexer} must only be used to tokenize one input at a time and
    never shared among threads.

    @return: The global L{QueryLexer} instance.
    """
    global _lexer
    if _lexer is None:
        lexer = QueryLexer()
        lexer.build()
        _lexer = lexer
    return _lexer


_illegalQueries = None


def getIllegalQueries():
    """Get a list of illegal L{Query}s.

    This function is used because this logic relies on configuration settings
    from L{fluiddb.application} to be properly setup.  This prevents us from
    using a module-level constant.

    @return: A C{list} of illegal L{Query}s.
    """
    global _illegalQueries
    if _illegalQueries is None:
        _illegalQueries = [_parseQuery('has fluiddb/about'),
                           _parseQuery('fluiddb/about matches ""')]
    return _illegalQueries
