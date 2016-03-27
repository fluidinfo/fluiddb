from twisted.internet import reactor
from twisted.internet.threads import deferToThreadPool

from fluiddb.exceptions import FeatureError
from fluiddb.query.grammar import (
    Node, QueryLexer, QueryParser, QueryParseError)
from fluiddb.query.parser import (
    IllegalQueryError, getQueryLexer, getQueryParser, parseQuery)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, ThreadPoolResource


class GetQueryParserTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('threadPool', ThreadPoolResource())]

    def testGetQueryParser(self):
        """
        L{getQueryParser} returns a L{QueryParser} instance suitable for
        parsing Fluidinfo queries.
        """
        parser = getQueryParser()
        self.assertTrue(isinstance(parser, QueryParser))

    def testGetQueryParserInThread(self):
        """
        L{getQueryParser} is not thread-safe.  A L{FeatureError} is raised if
        its called outside the main thread.
        """
        deferred = deferToThreadPool(reactor, self.threadPool, getQueryParser)
        return self.assertFailure(deferred, FeatureError)

    def testGetQueryParserCachesResult(self):
        """
        L{getQueryParser} only builds a single L{QueryParser} instance,
        because it's an expensive operation.  It returns the same instance
        each time its called.
        """
        self.assertIdentical(getQueryParser(), getQueryParser())


class GetQueryLexerTest(FluidinfoTestCase):

    def testGetQueryLexer(self):
        """
        L{getQueryLexer} returns a L{QueryLexer} instance suitable for parsing
        Fluidinfo queries.
        """
        lexer = getQueryLexer()
        self.assertTrue(isinstance(lexer, QueryLexer))

    def testGetQueryLexerCachesResult(self):
        """
        L{getQueryLexer} builds and caches a single L{QueryLexer} instance.
        It returns the same instance each time its called.
        """
        self.assertIdentical(getQueryLexer(), getQueryLexer())


class ParseQueryTest(FluidinfoTestCase):

    resources = [('config', ConfigResource())]

    def assertNode(self, node, kind, value, left=None, right=None):
        """Assert that a node contains the expected values.

        @param node: The L{Node} to check.
        @param kind: The expected L{Node} kind.
        @param value: The expected L{Node.value} value.
        @param left: Optionally, a C{bool} specifying whether or not a left
            L{Node} is expected.  Defaults to C{False}.
        @param right: Optionally, a C{bool} specifying whether or not a right
            L{Node} is expected.  Defaults to C{False}.
        """
        self.assertEqual(kind, node.kind)
        self.assertEqual(value, node.value)
        if left:
            self.assertNotIdentical(None, node.left)
        else:
            self.assertIdentical(None, node.left)
        if right:
            self.assertNotIdentical(None, node.right)
        else:
            self.assertIdentical(None, node.right)

    def testParseQueryResultIncludesText(self):
        """
        The L{Query} returned by L{parseQuery} includes the input text used to
        build the abstract syntax tree.
        """
        query = parseQuery('test/tag > 4')
        self.assertEqual('test/tag > 4', query.text)

    def testParseQueryWithIntComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  Integer values are
        automatically converted to C{int}.
        """
        rootNode = parseQuery('test/tag > 4').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 4)

    def testParseQueryWithInfinityComparison(self):
        """
        Very large numbers are converted to infinity during parsing, which in
        turn causes a L{QueryParseError} because we can't handle such queries.
        """
        self.assertRaises(QueryParseError, parseQuery, 'test/tag > 1e1000')

    def testParseQueryWithFalseBooleanComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  Boolean values are
        automatically converted to C{bool}.
        """
        rootNode = parseQuery('test/tag != false').rootNode
        self.assertNode(rootNode, Node.NEQ_OPERATOR, '!=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, False)

    def testParseQueryWithMixedCasePaths(self):
        """
        The first component of all paths is lowercased by the query parser. The
        rest of the path keeps the same case.
        """
        rootNode = parseQuery('TEST/Tag = 1').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, u'test/Tag')
        self.assertNode(rootNode.right, Node.VALUE, 1)

    def testParseQueryWithCaseInsensitiveFalseBooleanComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  Boolean values are
        matched case insensitively and automatically converted to C{bool}.
        """
        rootNode = parseQuery('test/tag != FaLsE').rootNode
        self.assertNode(rootNode, Node.NEQ_OPERATOR, '!=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, False)

    def testParseQueryWithPathBeginningWithFalseKeyword(self):
        """Paths that start with the C{false} keyword are correctly parsed."""
        rootNode = parseQuery('has falsetto/author').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'falsetto/author')

    def testParseQueryWithTrueBooleanComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  Boolean values are
        automatically converted to C{bool}.
        """
        rootNode = parseQuery('test/tag != true').rootNode
        self.assertNode(rootNode, Node.NEQ_OPERATOR, '!=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, True)

    def testParseQueryWithCaseInsensitiveTrueBooleanComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  Boolean values are
        matched case insensitively and automatically converted to C{bool}.
        """
        rootNode = parseQuery('test/tag != TrUe').rootNode
        self.assertNode(rootNode, Node.NEQ_OPERATOR, '!=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, True)

    def testParseQueryWithPathBeginningWithTrueKeyword(self):
        """Paths that start with the C{true} keyword are correctly parsed."""
        rootNode = parseQuery('has truethat.com/author').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'truethat.com/author')

    def testParseQueryWithNegativeIntComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  Integer values are
        automatically converted to C{int}.
        """
        rootNode = parseQuery('test/tag > -4').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, -4)

    def testParseQueryWithFloatComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  Floating-point values
        are automatically converted to C{float}.
        """
        rootNode = parseQuery('test/tag > 4.5').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 4.5)

    def testParseQueryWithNegativeFloatComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  Floating-point values
        are automatically converted to C{float}.
        """
        rootNode = parseQuery('test/tag > -4.5').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, -4.5)

    def testParseQueryWithTerseFloat(self):
        """A float without a leading zero is parsed correctly."""
        rootNode = parseQuery('test/tag > .5').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 0.5)

    def testParseQueryWithNegativeTerseFloat(self):
        """A negative float without a leading zero is parsed correctly."""
        rootNode = parseQuery('test/tag > -.5').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, -0.5)

    def testParseQueryWithUnicodeComparison(self):
        """
        A comparison query gets parsed into a tree with the operator at the
        root, path on the left and value on the right.  String values are
        automatically converted to C{unicode}.
        """
        rootNode = parseQuery('test/tag > "value"').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 'value')
        self.assertIsInstance(rootNode.right.value, unicode)

    def testParseQueryWithEqualityComparison(self):
        """
        The Fluidinfo query language supports equality comparisons with the
        C{=} symbol.
        """
        rootNode = parseQuery('test/tag = 4').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 4)

    def testParseQueryWithInequalityComparison(self):
        """
        The Fluidinfo query language supports inequality comparisons with the
        C{!=} symbol.
        """
        rootNode = parseQuery('test/tag != 4').rootNode
        self.assertNode(rootNode, Node.NEQ_OPERATOR, '!=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 4)

    def testParseQueryWithLessThanComparison(self):
        """
        The Fluidinfo query language supports less-than comparisons with the
        C{<} symbol.
        """
        rootNode = parseQuery('test/tag < 4').rootNode
        self.assertNode(rootNode, Node.LT_OPERATOR, '<', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 4)

    def testParseQueryWithLessThanOrEqualComparison(self):
        """
        The Fluidinfo query language supports less-than-or-equal comparisons
        with the C{<=} symbol.
        """
        rootNode = parseQuery('test/tag <= 4').rootNode
        self.assertNode(rootNode, Node.LTE_OPERATOR, '<=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 4)

    def testParseQueryWithGreaterThanComparison(self):
        """
        The Fluidinfo query language supports greater-than comparisons with
        the C{>} symbol.
        """
        rootNode = parseQuery('test/tag > 4').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 4)

    def testParseQueryWithGreaterThanOrEqualComparison(self):
        """
        The Fluidinfo query language supports greater-than-or-equal
        comparisons with the C{>=} symbol.
        """
        rootNode = parseQuery('test/tag >= 4').rootNode
        self.assertNode(rootNode, Node.GTE_OPERATOR, '>=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 4)

    def testParseQueryWithNullComparison(self):
        """
        The Fluidinfo query language supports comparison with the
        C{null} value, which is translated into Python's C{None}
        object.
        """
        rootNode = parseQuery('test/tag = null').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, None)

    def testParseQueryWithCaseInsensitiveNullComparison(self):
        """
        The Fluidinfo query language supports comparison with the
        C{null} value, which is translated into Python's C{None}
        object.
        """
        rootNode = parseQuery('test/tag = NuLl').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, None)

    def testParseQueryWithPathBeginningWithNullKeyword(self):
        """Paths that start with the C{null} keyword are correctly parsed."""
        rootNode = parseQuery('has null/tag').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'null/tag')

    def testParseQueryIgnoresWhitespaceWithComparison(self):
        """Whitespace is ignored in queries involving comparisons."""
        rootNode = parseQuery('test/tag>3').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 3)

    def testParseQueryIgnoresLeadingAndTrailingWhitespace(self):
        """Leading and trailing whitespace is ignored when parsing queries."""
        rootNode = parseQuery('    test/tag > 3    ').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 3)

    def testParseQueryWithUnknownBackslashInString(self):
        """
        An unknown backslash sequence in a string value is preserved during
        parsing.
        """
        rootNode = parseQuery('test/tag > "val\ue"').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 'val\ue')

    def testParseQueryWithTabCharacterSequenceInString(self):
        r"""
        The C{\t} character sequence is not interpreted as a tab character.
        It is preserved during parsing.
        """
        rootNode = parseQuery('test/tag > "val\\tue"').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, r'val\tue')

    def testParseQueryWithTabCharacterInString(self):
        """A leading tab is preserved during parsing."""
        rootNode = parseQuery('fluiddb/about = "esther\t dyson"').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'fluiddb/about')
        self.assertNode(rootNode.right, Node.VALUE, 'esther\t dyson')

    def testParseQueryWithLeadingTabCharacterInString(self):
        """A leading tab is preserved during parsing."""
        rootNode = parseQuery('fluiddb/about = "\testher dyson"').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'fluiddb/about')
        self.assertNode(rootNode.right, Node.VALUE, '\testher dyson')

    def testParseQueryWithTrailingTabCharacterInString(self):
        """A trailing tab is preserved during parsing."""
        rootNode = parseQuery('fluiddb/about = "esther dyson\t"').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'fluiddb/about')
        self.assertNode(rootNode.right, Node.VALUE, 'esther dyson\t')

    def testParseQueryWithNewlineCharacterSequenceInString(self):
        r"""
        The C{\n} character sequence is not interpreted as a newline
        character.  It is preserved during parsing.
        """
        rootNode = parseQuery('test/tag > "val\\nue"').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, r'val\nue')

    def testParseQueryWithNewlineCharacterInString(self):
        """A leading newline is preserved during parsing."""
        rootNode = parseQuery('fluiddb/about = "esther\n dyson"').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'fluiddb/about')
        self.assertNode(rootNode.right, Node.VALUE, 'esther\n dyson')

    def testParseQueryWithLeadingNewlineCharacterInString(self):
        """A leading newline is preserved during parsing."""
        rootNode = parseQuery('fluiddb/about = "\nesther dyson"').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'fluiddb/about')
        self.assertNode(rootNode.right, Node.VALUE, '\nesther dyson')

    def testParseQueryWithTrailingNewlineCharacterInString(self):
        """A trailing newline is preserved during parsing."""
        rootNode = parseQuery('fluiddb/about = "esther dyson\n"').rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'fluiddb/about')
        self.assertNode(rootNode.right, Node.VALUE, 'esther dyson\n')

    def testParseQueryWithUnescapedDoubleQuote(self):
        """
        A L{QueryParseError} is raised if a string literal contains an
        unescaped double-quote character.
        """
        self.assertRaises(QueryParseError, parseQuery, 'test/tag ="foo\n"bar"')

    def testParseQueryWithBackslashDoubleQuoteCharacter(self):
        r"""
        A backslash double-quote character, C{\"}, is converted to a plain
        double-quote during parsing.
        """
        rootNode = parseQuery('test/tag > "val\\"ue"').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 'val"ue')

    def testParseQueryWithMultipleBackslashDoubleQuoteCharacter(self):
        r'''
        Multiple backslash double-quote characters, C{\\"}, are converted to
        plain double-quotes during parsing.
        '''
        rootNode = parseQuery('test/tag > "val\\"ue anot\\"her"').rootNode
        self.assertNode(rootNode, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, 'val"ue anot"her')

    def testParseQueryWithHas(self):
        """
        A C{has} query gets parsed into a tree with the C{has} keyword at the
        root and the path on the left.
        """
        rootNode = parseQuery('has test/tag').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')

    def testParseQueryWithCaseInsensitiveHas(self):
        """
        A C{has} query is matched case insensitively and gets parsed into a
        tree with the C{has} keyword at the root and the path on the left.
        """
        rootNode = parseQuery('HaS test/tag').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')

    def testParseQueryWithMalformedHas(self):
        """
        A L{QueryParseError} is raised when a query specifies C{has}
        incorrectly.
        """
        self.assertRaises(QueryParseError, parseQuery, 'has')
        self.assertRaises(QueryParseError, parseQuery, 'has and')
        self.assertRaises(QueryParseError, parseQuery, 'has joe/x has')
        self.assertRaises(QueryParseError, parseQuery, 'has *')

    def testParseQueryWithPathContainingUnicodeCharacters(self):
        """Unicode characters in paths are correctly parsed."""
        path = u'\N{HIRAGANA LETTER A}/\N{HIRAGANA LETTER E}'
        rootNode = parseQuery('%s = "value"' % path).rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, path)
        self.assertNode(rootNode.right, Node.VALUE, 'value')

    def testParseQueryWithPathContainingDottedNamespace(self):
        """
        Paths that contain a dot in the root L{Namespace} are parsed
        correctly.
        """
        rootNode = parseQuery('has twitter.com/username').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'twitter.com/username')

    def testParseQueryWithPathContainingLeadingDotInNamespace(self):
        """
        Paths that contain a leading dot in the root L{Namespace} are parsed
        correctly.
        """
        rootNode = parseQuery('has .test/tag').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, '.test/tag')

    def testParseQueryWithPathContainingTrailingDotInNamespace(self):
        """
        Paths that contain a trailing dot in the root L{Namespace} are parsed
        correctly.
        """
        rootNode = parseQuery('has test./tag').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'test./tag')

    def testParseQueryWithPathContainingMultiplyDottedNamespace(self):
        """
        Paths that contain more than one dot in the root L{Namespace} are
        parsed correctly.
        """
        rootNode = parseQuery('has twitter.co.jp/username').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'twitter.co.jp/username')

    def testParseQueryWithPathContainingDottedTag(self):
        """Paths that contain a dot in a L{Tag} name are parsed correctly."""
        rootNode = parseQuery('has test/facebook.com').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'test/facebook.com')

    def testParseQueryWithPathContainingLeadingDotInTag(self):
        """
        Paths that contain a leading dot in a L{Tag} name are parsed
        correctly.
        """
        rootNode = parseQuery('has test/.tag').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'test/.tag')

    def testParseQueryWithPathContainingTrailingDotInTag(self):
        """
        Paths that contain a trailing dot in a L{Tag} name are parsed
        correctly.
        """
        rootNode = parseQuery('has test/tag.').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag.')

    def testParseQueryWithPathContainingMultiplyDottedTag(self):
        """
        Paths that contain more than one dot in a L{Tag} name are parsed
        correctly.
        """
        rootNode = parseQuery('has test/facebook.co.jp').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'test/facebook.co.jp')

    def testParseQueryWithPathContainingOnlyDots(self):
        """Paths that only contain dots are parsed correctly."""
        rootNode = parseQuery('has ./.').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, './.')

    def testParseQueryWithPathContainingOnlyMultipleDots(self):
        """Paths that only contain (multiple) dots are parsed correctly."""
        rootNode = parseQuery('has ../..').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, '../..')

    def testParseQueryWithPathContainingMixedCase(self):
        """
        Paths that contain mixed upper and lower case are not altered during
        parsing.
        """
        rootNode = parseQuery('has lower/UPPER/MiXeD').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'lower/UPPER/MiXeD')

    def testParseQueryWithPathBeginningWithOrKeyword(self):
        """Paths that start with the C{or} keyword are correctly parsed."""
        rootNode = parseQuery('has oreilly.com/author').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'oreilly.com/author')

    def testParseQueryWithPathBeginningWithAndKeyword(self):
        """Paths that start with the C{and} keyword are correctly parsed."""
        rootNode = parseQuery('has android.com/model').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'android.com/model')

    def testParseQueryWithPathBeginningWithExceptKeyword(self):
        """Paths that start with the C{except} keyword are correctly parsed."""
        rootNode = parseQuery('has exception/error-class').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'exception/error-class')

    def testParseQueryWithPathBeginningWithMatchesKeyword(self):
        """
        Paths that start with the C{matches} keyword are correctly parsed.
        """
        rootNode = parseQuery('has matchstick/length').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'matchstick/length')

    def testParseQueryWithPathBeginningWithHasKeyword(self):
        """Paths that start with the C{has} keyword are correctly parsed."""
        rootNode = parseQuery('has hasbro.com/toy').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'hasbro.com/toy')

    def testParseQueryWithPathBeginningWithContainsKeyword(self):
        """
        Paths that start with the C{contains} keyword are correctly parsed.
        """
        rootNode = parseQuery('has contains.com/id').rootNode
        self.assertNode(rootNode, Node.HAS, 'has', True)
        self.assertNode(rootNode.left, Node.PATH, 'contains.com/id')

    def testParseQueryWithMalformedPath(self):
        """
        A L{QueryParseError} is raised if a malformed path is included in a
        query.
        """
        self.assertRaises(QueryParseError, parseQuery, 'test/ > 4')
        self.assertRaises(QueryParseError, parseQuery, '/ > 4')
        self.assertRaises(QueryParseError, parseQuery, 't > 4')
        self.assertRaises(QueryParseError, parseQuery, '5 > 4')

    def testParseQueryWithValueContainingUnicodeCharacters(self):
        """Unicode characters in values are correctly parsed."""
        value = u'\N{HIRAGANA LETTER A}/\N{HIRAGANA LETTER E}'
        rootNode = parseQuery('test/tag = "%s"' % value).rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, value)

    def testParseQueryWithValueContainingUnicodeControlCharacters(self):
        """
        Unicode control characters in values are preserved during parsing.
        This is arguably a bug and shouldn't be supported, but for now it is.
        """
        value = u'\u001f \u007f'
        rootNode = parseQuery('test/tag = "%s"' % value).rootNode
        self.assertNode(rootNode, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.VALUE, value)

    def testParseQueryWithMatches(self):
        """
        A C{matches} query gets parsed into a tree with the C{matches}
        operator at the root, path on the left and value on the right.
        """
        rootNode = parseQuery('test/tag matches "term"').rootNode
        self.assertNode(rootNode, Node.MATCHES, 'matches', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.KEY, 'term')

    def testParseQueryWithCaseInsensitiveMatches(self):
        """
        A C{matches} query is matched case insensitively and gets parsed into
        a tree with the C{matches} operator at the root, path on the left and
        value on the right.
        """
        rootNode = parseQuery('test/tag MaTcHeS "term"').rootNode
        self.assertNode(rootNode, Node.MATCHES, 'matches', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.KEY, 'term')

    def testParseQueryWithMalformedMatches(self):
        """
        A L{QueryParseError} is raised when a query specifies C{matches}
        incorrectly.
        """
        self.assertRaises(QueryParseError, parseQuery, 'matches')
        self.assertRaises(QueryParseError, parseQuery, 'matches term')
        self.assertRaises(QueryParseError, parseQuery, 'test/tag matches term')
        self.assertRaises(QueryParseError, parseQuery, 'test/tag matches')

    def testParseQueryWithContains(self):
        """
        A C{contains} query gets parsed into a tree with the C{contains}
        operator at the root, path on the left and value on the right.
        """
        rootNode = parseQuery('test/tag contains "value"').rootNode
        self.assertNode(rootNode, Node.CONTAINS, 'contains', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.KEY, 'value')

    def testParseQueryWithCaseInsensitiveContains(self):
        """
        A C{contains} query is matched case insensitively and gets parsed into
        a tree with the C{contains} operator at the root, path on the left and
        value on the right.
        """
        rootNode = parseQuery('test/tag CoNtAiNs "value"').rootNode
        self.assertNode(rootNode, Node.CONTAINS, 'contains', True, True)
        self.assertNode(rootNode.left, Node.PATH, 'test/tag')
        self.assertNode(rootNode.right, Node.KEY, 'value')

    def testParseQueryWithMalformedContains(self):
        """
        A L{QueryParseError} is raised when a query specifies C{contains}
        incorrectly.
        """
        self.assertRaises(QueryParseError, parseQuery, 'contains')
        self.assertRaises(QueryParseError, parseQuery, 'test/tag contains')

    def testParseQueryWithExcept(self):
        """
        An C{except} query gets parsed into a tree with the C{except} operator
        at the root, conditional expression on the left and exceptional
        expression on the right.
        """
        rootNode = parseQuery('test/tag1 > 5 except has test/tag2').rootNode
        self.assertNode(rootNode, Node.EXCEPT, 'except', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(leftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftExpression.right, Node.VALUE, 5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.HAS, 'has', True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag2')

    def testParseQueryWithCaseInsensitiveExcept(self):
        """
        An C{except} query is matched case insensitively and gets parsed into
        a tree with the C{except} operator at the root, conditional expression
        on the left and exceptional expression on the right.
        """
        rootNode = parseQuery('test/tag1 > 5 ExCepT has test/tag2').rootNode
        self.assertNode(rootNode, Node.EXCEPT, 'except', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(leftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftExpression.right, Node.VALUE, 5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.HAS, 'has', True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag2')

    def testParseQueryWithMalformedExcept(self):
        """
        A L{QueryParseError} is raised when a query specifies C{except}
        incorrectly.
        """
        self.assertRaises(QueryParseError, parseQuery, 'except')
        self.assertRaises(QueryParseError, parseQuery, 'test/tag except')

    def testParseQueryWithExceptAndContains(self):
        """
        The C{except} operator has higher precedence than the C{contains}
        operator.
        """
        query = parseQuery('has test/tag1 except test/tag2 contains "value"')
        rootNode = query.rootNode
        self.assertNode(rootNode, Node.EXCEPT, 'except', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.HAS, 'has', True)
        self.assertNode(leftExpression.left, Node.PATH, 'test/tag1')

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.CONTAINS, 'contains', True, True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag2')
        self.assertNode(rightExpression.right, Node.KEY, 'value')

    def testParseQueryWithExceptAndOr(self):
        """
        The C{or} operator has higher precendence than the C{except} operator.
        """
        query = parseQuery('test/tag1 < 5 except test/tag2 = 8.5 or '
                           'has test/tag3')
        rootNode = query.rootNode
        self.assertNode(rootNode, Node.OR, 'or', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.EXCEPT, 'except', True, True)
        leftLeftExpression = leftExpression.left
        self.assertNode(leftLeftExpression, Node.LT_OPERATOR, '<', True, True)
        self.assertNode(leftLeftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftLeftExpression.right, Node.VALUE, 5)
        leftRightExpression = leftExpression.right
        self.assertNode(leftRightExpression, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(leftRightExpression.left, Node.PATH, 'test/tag2')
        self.assertNode(leftRightExpression.right, Node.VALUE, 8.5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.HAS, 'has', True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag3')

    def testParseQueryWithOrAndExcept(self):
        """
        The C{or} operator has higher precendence than the C{except} operator.
        """
        query = parseQuery('test/tag1 < 5 or test/tag2 = 8.5 '
                           'except has test/tag3 or test/tag4 > "value"')
        rootNode = query.rootNode
        self.assertNode(rootNode, Node.OR, 'or', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.OR, 'or', True, True)
        leftLeftExpression = leftExpression.left
        self.assertNode(leftLeftExpression, Node.LT_OPERATOR, '<', True, True)
        self.assertNode(leftLeftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftLeftExpression.right, Node.VALUE, 5)
        leftRightExpression = leftExpression.right
        self.assertNode(leftRightExpression, Node.EXCEPT, 'except', True,
                        True)
        leftRightLeftExpression = leftRightExpression.left
        self.assertNode(leftRightLeftExpression, Node.EQ_OPERATOR, '=', True,
                        True)
        self.assertNode(leftRightLeftExpression.left, Node.PATH, 'test/tag2')
        self.assertNode(leftRightLeftExpression.right, Node.VALUE, 8.5)
        leftRightRightExpression = leftRightExpression.right
        self.assertNode(leftRightRightExpression, Node.HAS, 'has', True)
        self.assertNode(leftRightRightExpression.left, Node.PATH, 'test/tag3')

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag4')
        self.assertNode(rightExpression.right, Node.VALUE, 'value')

    def testParseQueryWithExceptAndOrWithParentheses(self):
        """
        Parentheses may be used to define explicit precedence for expressions
        in a query.
        """
        query = parseQuery('(test/tag1 < 5 or test/tag2 = 8.5) except '
                           '(has test/tag3 or test/tag4 > "value")')
        rootNode = query.rootNode
        self.assertNode(rootNode, Node.EXCEPT, 'except', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.OR, 'or', True, True)
        leftLeftExpression = leftExpression.left
        self.assertNode(leftLeftExpression, Node.LT_OPERATOR, '<', True, True)
        self.assertNode(leftLeftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftLeftExpression.right, Node.VALUE, 5)
        leftRightExpression = leftExpression.right
        self.assertNode(leftRightExpression, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(leftRightExpression.left, Node.PATH, 'test/tag2')
        self.assertNode(leftRightExpression.right, Node.VALUE, 8.5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.OR, 'or', True, True)
        rightLeftExpression = rightExpression.left
        self.assertNode(rightLeftExpression, Node.HAS, 'has', True)
        self.assertNode(rightLeftExpression.left, Node.PATH, 'test/tag3')
        rightRightExpression = rightExpression.right
        self.assertNode(rightRightExpression, Node.GT_OPERATOR, '>', True,
                        True)
        self.assertNode(rightRightExpression.left, Node.PATH, 'test/tag4')
        self.assertNode(rightRightExpression.right, Node.VALUE, 'value')

    def testParseQueryWithAnd(self):
        """
        An C{and} query gets parsed into a tree with the C{and} operator at
        the root, first expression on the left and second expression on the
        right.
        """
        rootNode = parseQuery('test/tag1 > 5 and has test/tag2').rootNode
        self.assertNode(rootNode, Node.AND, 'and', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(leftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftExpression.right, Node.VALUE, 5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.HAS, 'has', True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag2')

    def testParseQueryWithCaseInsensitiveAnd(self):
        """
        An C{and} query is matched case insensitively and gets parsed into a
        tree with the C{and} operator at the root, first expression on the
        left and second expression on the right.
        """
        rootNode = parseQuery('test/tag1 > 5 AnD has test/tag2').rootNode
        self.assertNode(rootNode, Node.AND, 'and', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(leftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftExpression.right, Node.VALUE, 5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.HAS, 'has', True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag2')

    def testParseQueryWithMalformedAnd(self):
        """
        A L{QueryParseError} is raised if a query specified C{and}
        incorrectly.
        """
        self.assertRaises(QueryParseError, parseQuery, 'and')
        self.assertRaises(QueryParseError, parseQuery, 'and > 4')

    def testParseQueryWithAndAndString(self):
        """
        The query here will cause an infinite loop in L{QueryParser} if the
        C{t_STRING} regular expression isn't written in a way that handles
        newlines in a robust way.
        """
        query = 'user/tag1 = "string" and user/tag2 = 5 and user/tag3 = 5.5'
        rootNode = parseQuery(query).rootNode
        self.assertNode(rootNode, Node.AND, 'and', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.AND, 'and', True, True)

        leftAndLeftExpression = leftExpression.left
        self.assertNode(leftAndLeftExpression, Node.EQ_OPERATOR, '=', True,
                        True)
        self.assertNode(leftAndLeftExpression.left, Node.PATH, 'user/tag1')
        self.assertNode(leftAndLeftExpression.right, Node.VALUE, u'string')

        rightAndLeftExpression = leftExpression.right
        self.assertNode(rightAndLeftExpression, Node.EQ_OPERATOR, '=', True,
                        True)
        self.assertNode(rightAndLeftExpression.left, Node.PATH, 'user/tag2')
        self.assertNode(rightAndLeftExpression.right, Node.VALUE, 5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rightExpression.left, Node.PATH, 'user/tag3')
        self.assertNode(rightExpression.right, Node.VALUE, 5.5)

    def testParseQueryWithOr(self):
        """
        An C{or} query gets parsed into a tree with the C{or} operator at the
        root, first expression on the left and second expression on the right.
        """
        rootNode = parseQuery('test/tag1 > 5 or has test/tag2').rootNode
        self.assertNode(rootNode, Node.OR, 'or', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(leftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftExpression.right, Node.VALUE, 5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.HAS, 'has', True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag2')

    def testParseQueryWithCaseInsensitiveOr(self):
        """
        An C{or} query is matched case insensitively and gets parsed into a
        tree with the C{or} operator at the root, first expression on the left
        and second expression on the right.
        """
        rootNode = parseQuery('test/tag1 > 5 oR has test/tag2').rootNode
        self.assertNode(rootNode, Node.OR, 'or', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(leftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftExpression.right, Node.VALUE, 5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.HAS, 'has', True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag2')

    def testParseQueryWithMalformedOr(self):
        """
        A L{QueryParseError} is raised if a query specified C{or} incorrectly.
        """
        self.assertRaises(QueryParseError, parseQuery, 'or')
        self.assertRaises(QueryParseError, parseQuery, 'or > 4')

    def testParseQueryWithAndMixedWithOr(self):
        """The C{or} operator has higher precendence than C{and}."""
        query = parseQuery('test/tag1 < 5 and test/tag2 = 8.5 or '
                           'has test/tag3 and test/tag4 > "value"')
        rootNode = query.rootNode
        self.assertNode(rootNode, Node.OR, 'or', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.AND, 'and', True, True)
        leftAndExpression = leftExpression.left
        self.assertNode(leftAndExpression, Node.LT_OPERATOR, '<', True, True)
        self.assertNode(leftAndExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftAndExpression.right, Node.VALUE, 5)
        rightAndExpression = leftExpression.right
        self.assertNode(rightAndExpression, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(rightAndExpression.left, Node.PATH, 'test/tag2')
        self.assertNode(rightAndExpression.right, Node.VALUE, 8.5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.AND, 'and', True, True)
        leftAndExpression = rightExpression.left
        self.assertNode(leftAndExpression, Node.HAS, 'has', True)
        self.assertNode(leftAndExpression.left, Node.PATH, 'test/tag3')
        rightAndExpression = rightExpression.right
        self.assertNode(rightAndExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rightAndExpression.left, Node.PATH, 'test/tag4')
        self.assertNode(rightAndExpression.right, Node.VALUE, 'value')

    def testParseQueryWithOrMixedWithAnd(self):
        """The C{or} operator has higher precendence than C{and}."""
        query = parseQuery('test/tag1 < 5 or test/tag2 = 8.5 and '
                           'has test/tag3 or test/tag4 > "value"')
        rootNode = query.rootNode
        self.assertNode(rootNode, Node.OR, 'or', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.OR, 'or', True, True)
        leftOrExpression = leftExpression.left
        self.assertNode(leftOrExpression, Node.LT_OPERATOR, '<', True, True)
        self.assertNode(leftOrExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftOrExpression.right, Node.VALUE, 5)
        rightOrExpression = leftExpression.right
        self.assertNode(rightOrExpression, Node.AND, 'and', True, True)
        rightOrLeftExpression = rightOrExpression.left
        self.assertNode(rightOrLeftExpression, Node.EQ_OPERATOR, '=', True,
                        True)
        self.assertNode(rightOrLeftExpression.left, Node.PATH, 'test/tag2')
        self.assertNode(rightOrLeftExpression.right, Node.VALUE, 8.5)
        rightOrRightExpression = rightOrExpression.right
        self.assertNode(rightOrRightExpression, Node.HAS, 'has', True)
        self.assertNode(rightOrRightExpression.left, Node.PATH, 'test/tag3')

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.GT_OPERATOR, '>', True, True)
        self.assertNode(rightExpression.left, Node.PATH, 'test/tag4')
        self.assertNode(rightExpression.right, Node.VALUE, 'value')

    def testParseQueryWithOrMixedWithAndAndParentheses(self):
        """
        Parentheses may be used to define explicit precedence for expressions
        in a query.
        """
        query = parseQuery('(test/tag1 < 5 or test/tag2 = 8.5) and '
                           '(has test/tag3 or test/tag4 > "value")')
        rootNode = query.rootNode
        self.assertNode(rootNode, Node.AND, 'and', True, True)

        leftExpression = rootNode.left
        self.assertNode(leftExpression, Node.OR, 'or', True, True)
        leftLeftExpression = leftExpression.left
        self.assertNode(leftLeftExpression, Node.LT_OPERATOR, '<', True, True)
        self.assertNode(leftLeftExpression.left, Node.PATH, 'test/tag1')
        self.assertNode(leftLeftExpression.right, Node.VALUE, 5)
        leftRightExpression = leftExpression.right
        self.assertNode(leftRightExpression, Node.EQ_OPERATOR, '=', True, True)
        self.assertNode(leftRightExpression.left, Node.PATH, 'test/tag2')
        self.assertNode(leftRightExpression.right, Node.VALUE, 8.5)

        rightExpression = rootNode.right
        self.assertNode(rightExpression, Node.OR, 'or', True, True)
        rightLeftExpression = rightExpression.left
        self.assertNode(rightLeftExpression, Node.HAS, 'has', True)
        self.assertNode(rightLeftExpression.left, Node.PATH, 'test/tag3')
        rightRightExpression = rightExpression.right
        self.assertNode(rightRightExpression, Node.GT_OPERATOR, '>', True,
                        True)
        self.assertNode(rightRightExpression.left, Node.PATH, 'test/tag4')
        self.assertNode(rightRightExpression.right, Node.VALUE, 'value')

    def testParseQueryWithHasFluiddbSlashAbout(self):
        """
        L{parseQuery} raises an L{IllegalQueryError} if the query to parse
        contains a C{has fluiddb/about} expression.
        """
        self.assertRaises(IllegalQueryError, parseQuery, 'has fluiddb/about')

    def testParseQueryWithFluiddbSlashAboutMatchesEmptyString(self):
        """
        L{parseQuery} raises an L{IllegalQueryError} if the query to parse
        contains a C{fluiddb/about matches ""} expression.
        """
        self.assertRaises(IllegalQueryError, parseQuery,
                          'fluiddb/about matches ""')


class QueryTest(FluidinfoTestCase):

    resources = [('config', ConfigResource())]

    def testGetPathsWithEqualsComparison(self):
        """
        L{Query.getPath}s returns the L{Tag.path} in equality expressions.
        """
        query = parseQuery('test/tag = 5')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithNotEqualsComparison(self):
        """
        L{Query.getPath}s returns the L{Tag.path} in inequality expressions.
        """
        query = parseQuery('test/tag != 5')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithLessThanComparison(self):
        """
        L{Query.getPath}s returns the L{Tag.path} in less-than expressions.
        """
        query = parseQuery('test/tag < 5')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithLessThanOrEqualsComparison(self):
        """
        L{Query.getPath}s returns the L{Tag.path} in less-than-or-equal
        expressions.
        """
        query = parseQuery('test/tag <= 5')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithGreaterThanComparison(self):
        """
        L{Query.getPath}s returns the L{Tag.path} in greater-than expressions.
        """
        query = parseQuery('test/tag > 5')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithGreaterThanOrEqualsComparison(self):
        """
        L{Query.getPath}s returns the L{Tag.path} in greater-than-or-equal
        expressions.
        """
        query = parseQuery('test/tag >= 5')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithHas(self):
        """L{Query.getPath}s returns the L{Tag.path} in C{has} expressions."""
        query = parseQuery('has test/tag')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithContains(self):
        """
        L{Query.getPath}s returns the L{Tag.path} in C{contains} expressions.
        """
        query = parseQuery('test/tag contains "value"')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithMatches(self):
        """
        L{Query.getPath}s returns the L{Tag.path} in C{matches} expressions.
        """
        query = parseQuery('test/tag matches "value"')
        self.assertEqual(set([u'test/tag']), query.getPaths())

    def testGetPathsWithAnd(self):
        """L{Query.getPath}s returns the L{Tag.path}s in C{and} expressions."""
        query = parseQuery('test/tag1 < 5 and test/tag2 = 8.5')
        self.assertEqual(set([u'test/tag1', u'test/tag2']), query.getPaths())

    def testGetPathsWithOr(self):
        """L{Query.getPath}s returns the L{Tag.path}s in C{or} expressions."""
        query = parseQuery('test/tag1 < 5 or test/tag2 = 8.5')
        self.assertEqual(set([u'test/tag1', u'test/tag2']), query.getPaths())

    def testGetPathsWithExcept(self):
        """
        L{Query.getPath}s returns the L{Tag.path}s in C{except} expressions.
        """
        query = parseQuery('test/tag1 < 5 except test/tag2 = 8.5')
        self.assertEqual(set([u'test/tag1', u'test/tag2']), query.getPaths())

    def testContains(self):
        """
        L{Query.contains} returns C{True} if the specified expression exists
        in the parse tree.
        """
        query = parseQuery('has user/tag')
        self.assertTrue(query.contains(query))

    def testContainsWithoutMatch(self):
        """
        L{Query.contains} returns C{False} if the specified expression doesn't
        have a match in the parse tree.
        """
        query1 = parseQuery('has user/tag1')
        query2 = parseQuery('has user/tag2')
        self.assertFalse(query1.contains(query2))
        self.assertFalse(query2.contains(query1))

    def testContainsSubexpression(self):
        """
        L{Query.contains} returns C{True} if the specified query matches a
        subexpression in the parse tree.
        """
        query1 = parseQuery('has user/tag2')
        query2 = parseQuery('has user/tag1 or has user/tag2')
        self.assertTrue(query2.contains(query1))

    def testContainsWithNestedSubexpression(self):
        """
        L{Query.contains} returns C{True} if the specified query matches a
        subexpression nested deep in the parse tree.
        """
        query1 = parseQuery('has user/tag3')
        query2 = parseQuery('user/tag1 < 5 and user/tag2 = 8.5 or '
                            'has user/tag3 and user/tag4 > "value"')
        self.assertTrue(query2.contains(query1))

    def testContainsWithComplexQuery(self):
        """
        L{Query.contains} raises a L{FeatureError} if the L{Query} to match
        contains more than a single expression.
        """
        query = parseQuery('has user/tag1 or has user/tag2')
        self.assertRaises(FeatureError, query.contains, query)


class NodeTest(FluidinfoTestCase):

    def testEquality(self):
        """
        Two L{Node}s are consider equal if they have the same kind and value.
        """
        node = Node(Node.PATH, u'user/tag', None, None)
        self.assertEquals(node, node)

    def testEqualityWithDifferentSubtrees(self):
        """
        The subtrees a L{Node} has are not considered when performing equality
        checks.
        """
        node1 = Node(Node.PATH, u'user/tag',
                     Node(Node.MATCHES, u'foobar', None, None),
                     Node(Node.HAS, u'user/tag', None, None))
        node2 = Node(Node.PATH, u'user/tag', None, None)
        self.assertEquals(node1, node2)

    def testEqualityWithoutMatchingKinds(self):
        """
        Both the kind and value must be the same for two L{Node}s to be
        considered equivalent.
        """
        node1 = Node(Node.HAS, u'user/tag', None, None)
        node2 = Node(Node.PATH, u'user/tag', None, None)
        self.assertNotEquals(node1, node2)

    def testEqualityWithoutMatchingValues(self):
        """
        Both the kind and value must be the same for two L{Node}s to be
        considered equivalent.
        """
        node1 = Node(Node.PATH, u'user/tag1', None, None)
        node2 = Node(Node.PATH, u'user/tag2', None, None)
        self.assertNotEquals(node1, node2)
