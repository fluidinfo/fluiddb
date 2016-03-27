"""A PLY-based grammar for the Fluidinfo query language."""

from math import isinf
import re

from ply.lex import lex
from ply.yacc import yacc

from fluiddb.util.constant import Constant


class QueryParseError(Exception):
    """Raised when an error occurs while parsing a Fluidinfo query."""

    def __init__(self, message):
        self.message = message


BACKSLASH_QUOTE_REGEXP = re.compile(r'\\(?<!\\\\)"')


class QueryLexer(object):
    """A lexer for the Fluidinfo query language."""

    tokens = ['STRING', 'FLOAT', 'NUM', 'NULL', 'TRUE', 'FALSE', 'AND', 'OR',
              'LPAREN', 'RPAREN', 'HAS', 'LTE', 'LT', 'NEQ', 'EQ', 'GT', 'GTE',
              'PATH', 'CONTAINS', 'MATCHES', 'EXCEPT']

    t_LPAREN = r'\('
    t_RPAREN = r'\)'
    t_LTE = r'<='
    t_LT = r'<'
    t_NEQ = r'!='
    t_EQ = r'='
    t_GT = r'>'
    t_GTE = r'>='

    # PATH must be at the top to avoid problems with paths that start with
    # any of the keywords (except, contains, matches, or, and, has). PLY adds
    # the lexer rules in the same order as they are defined:
    #
    # See http://www.dabeaz.com/ply/ply.html#ply_nn6
    #
    # Quoting the documentation:
    #
    # When building the master regular expression, rules are added in the
    # following order:
    #
    # 1. All tokens defined by functions are added in the same order as they
    #    appear in the lexer file.
    #
    # 2. Tokens defined by strings are added next by sorting them in order of
    #    decreasing regular expression length (longer expressions are added
    #    first).
    def t_PATH(self, token):
        r'[\:\.\-\w]+(/[\:\.\-\w]+)+'
        return token

    def t_EXCEPT(self, token):
        r'(?i)except'
        token.value = token.value.lower()
        return token

    def t_CONTAINS(self, token):
        r'(?i)contains'
        token.value = token.value.lower()
        return token

    def t_MATCHES(self, token):
        r'(?i)matches'
        token.value = token.value.lower()
        return token

    def t_OR(self, token):
        r'(?i)or'
        token.value = token.value.lower()
        return token

    def t_AND(self, token):
        r'(?i)and'
        token.value = token.value.lower()
        return token

    def t_HAS(self, token):
        r'(?i)has'
        token.value = token.value.lower()
        return token

    def t_NULL(self, token):
        r'(?i)null'
        token.value = None
        return token

    def t_TRUE(self, token):
        r'(?i)true'
        token.value = True
        return token

    def t_FALSE(self, token):
        r'(?i)false'
        token.value = False
        return token

    def t_STRING(self, token):
        r'"([^"\\]|\\.)*"'
        # Strip the outer quotes and replace all instances of \" with ".
        value = re.sub(BACKSLASH_QUOTE_REGEXP, '"', token.value[1:-1])
        token.value = unicode(value)
        return token

    def t_FLOAT(self, token):
        r'-?((\d*)(\.\d+)(e(\+|-)?(\d+))? | (\d+)e(\+|-)?(\d+))([lL]|[fF])?'
        try:
            token.value = float(token.value)
        except ValueError:
            raise QueryParseError('Line %d: Number %s is too large!'
                                  % (token.lineno, token.value))
        if isinf(token.value):
            raise QueryParseError("Line %d: Infinity is not an acceptable "
                                  'number.' % token.lineno)
        return token

    def t_NUM(self, token):
        r'-?\d+'
        try:
            token.value = int(token.value)
            return token
        except ValueError:
            raise QueryParseError('Line %d: Number %s is too large!'
                                  % (token.lineno, token.value))

    t_ignore = " \t"

    def t_newline(self, token):
        r'\n+'
        token.lexer.lineno += token.value.count("\n")

    def t_error(self, token):
        """Handle a token parsing error.

        @param token: The token that couldn't be processed.
        @raise QueryParseError: Raised with information about the error.
        """
        raise QueryParseError('Illegal character %r.' % token.value[0])

    def build(self, **kwargs):
        """Build the lexer."""
        self.lexer = lex(reflags=re.UNICODE, object=self, **kwargs)


class QueryParser(object):
    """A parser for the Fluidinfo query language.

    @param tokens: The tokens defined by L{QueryLexer}.
    """

    precedence = [('right', 'HAS'),
                  ('left', 'OR'),
                  ('left', 'AND'),
                  ('left', 'EXCEPT'),
                  ('left', 'CONTAINS'),
                  ('left', 'MATCHES'),
                  ('left', 'LTE'),
                  ('left', 'GTE'),
                  ('left', 'NEQ'),
                  ('left', 'EQ'),
                  ('left', 'LT'),
                  ('left', 'GT')]

    def __init__(self, tokens):
        self.tokens = tokens

    def p_statement_expr(self, production):
        """statement : expression"""
        production[0] = production[1]

    def p_expression_neq_operator(self, production):
        """expression : path NEQ value"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.NEQ_OPERATOR, value, left, right)

    def p_expression_eq_operator(self, production):
        """expression : path EQ value"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.EQ_OPERATOR, value, left, right)

    def p_expression_lt_operator(self, production):
        """expression : path LT value"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.LT_OPERATOR, value, left, right)

    def p_expression_lte_operator(self, production):
        """expression : path LTE value"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.LTE_OPERATOR, value, left, right)

    def p_expression_gte_operator(self, production):
        """expression : path GTE value"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.GTE_OPERATOR, value, left, right)

    def p_expression_gt_operator(self, production):
        """expression : path GT value"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.GT_OPERATOR, value, left, right)

    def p_expression_group(self, production):
        """expression : LPAREN expression RPAREN"""
        production[0] = production[2]

    def p_expression_or(self, production):
        """expression : expression OR expression"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.OR, value, left, right)

    def p_expression_and(self, production):
        """expression : expression AND expression"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.AND, value, left, right)

    def p_expression_except(self, production):
        """expression : expression EXCEPT expression"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.EXCEPT, value, left, right)

    def p_expression_has(self, production):
        """expression : HAS path"""
        value = production[1]
        left = production[2]
        production[0] = Node(Node.HAS, value, left, None)

    def p_expression_contains(self, production):
        """expression : path CONTAINS key"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.CONTAINS, value, left, right)

    def p_expression_matches(self, production):
        """expression : path MATCHES key"""
        value = production[2]
        left = production[1]
        right = production[3]
        production[0] = Node(Node.MATCHES, value, left, right)

    def p_expression_value(self, production):
        """
        value : STRING
                | FLOAT
                | NUM
                | NULL
                | TRUE
                | FALSE
        """
        value = production[1]
        production[0] = Node(Node.VALUE, value, None, None)

    def p_expression_key(self, production):
        """key : STRING"""
        value = production[1]
        production[0] = Node(Node.KEY, value, None, None)

    def p_expression_path(self, production):
        """path : PATH"""
        value = production[1]

        # Lowercase the first component of the path.
        root, rest = value.split(u'/', 1)
        value = u'/'.join([root.lower(), rest])

        production[0] = Node(Node.PATH, value, None, None)

    def p_error(self, production):
        """Handle a parse error.

        @param production: The C{YaccProduction} that can't be parsed.
        @raise QueryParseError: Raised to signal the error.
        """
        if hasattr(production, 'value'):
            raise QueryParseError('Syntax error: production.value = %r'
                                  % production.value)
        else:
            raise QueryParseError("Syntax error: production has no value tag.")

    def build(self, **kwargs):
        """Build the parser."""
        self._yacc = yacc(**kwargs)

    def parse(self, query, lexer):
        """Parse a Fluidinfo query.

        @param query: A C{unicode} Fluidinfo query.
        @param lexer: The L{QueryLexer} instance to use when parsing queries.
        @raise QueryParseError: Raised if an error occurs while parsing the
            query.
        @return: A L{Node} representing the root node in the abstract syntax
            tree generated for the parsed query.
        """
        return self._yacc.parse(input=query, lexer=lexer)


class Node(object):
    """A node in the abstract syntax tree for a parsed Fluidinfo query.

    @param kind: The kind of L{Node}, such as L{Node.PATH} or L{Node.OR}, for
        example.
    @param value: The value (C{int}, C{string}, etc.) or the symbol for the
        node (C{>}, C{=}, etc.)
    @param left: The L{Node} on the left edge or C{None} if there is no left
        edge.
    @param right: The L{Node} on the right edge or C{None} if there is no
        right edge.
    """

    EQ_OPERATOR = Constant(0, 'EQ_OPERATOR')
    NEQ_OPERATOR = Constant(1, 'NEQ_OPERATOR')
    LT_OPERATOR = Constant(2, 'LT_OPERATOR')
    LTE_OPERATOR = Constant(3, 'LTE_OPERATOR')
    GT_OPERATOR = Constant(4, 'GT_OPERATOR')
    GTE_OPERATOR = Constant(5, 'GTE_OPERATOR')
    PATH = Constant(6, 'PATH')
    VALUE = Constant(7, 'VALUE')
    HAS = Constant(8, 'HAS')
    KEY = Constant(9, 'KEY')
    CONTAINS = Constant(10, 'CONTAINS')
    MATCHES = Constant(11, 'MATCHES')
    EXCEPT = Constant(12, 'EXCEPT')
    AND = Constant(13, 'AND')
    OR = Constant(14, 'OR')

    def __init__(self, kind, value, left, right):
        self.kind = kind
        self.value = value
        self.left = left
        self.right = right

    def __eq__(self, node):
        """Determine if another L{Node} is equivalent to this one.

        @param node: The other L{Node} to check.
        @return: C{True} if they're equal, otherwise C{False}.
        """
        return (self.kind == node.kind and self.value == node.value)

    def __repr__(self):
        """Get a printable representation of this node."""
        left = self.left if self.left is None else 'Node(%s)' % self.left.kind
        right = (
            self.right if self.right is None else 'Node(%s)' % self.right.kind)
        return ('<Node(%s) value=%r left=%s right=%s>'
                % (self.kind, self.value, left, right))
