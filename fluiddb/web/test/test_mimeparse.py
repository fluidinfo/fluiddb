from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.web.mimeparse import quality, best_match, parse_media_range

# Apart from some line wrapping, these tests are taken verbatim from the
# bottom of ../mimetypes.py


class TestMimeParsing(FluidinfoTestCase):

    def test_parse_media_range(self):
        self.assert_(('application', 'xml', {'q': '1'}) ==
                     parse_media_range('application/xml;q=1'))
        self.assertEqual(('application', 'xml', {'q': '1'}),
                         parse_media_range('application/xml'))
        self.assertEqual(('application', 'xml', {'q': '1'}),
                         parse_media_range('application/xml;q='))
        self.assertEqual(('application', 'xml', {'q': '1'}),
                         parse_media_range('application/xml ; q='))
        self.assertEqual(('application', 'xml', {'q': '1', 'b': 'other'}),
                         parse_media_range('application/xml ; q=1;b=other'))
        self.assertEqual(('application', 'xml', {'q': '1', 'b': 'other'}),
                         parse_media_range('application/xml ; q=2;b=other'))
        # Java URLConnection class sends an Accept header that includes a
        # single *
        self.assertEqual(('*', '*', {'q': '.2'}),
                         parse_media_range(" *; q=.2"))

    def test_rfc_2616_example(self):
        accept = "text/*;q=0.3, text/html;q=0.7, text/html;level=1, " \
                 "text/html;level=2;q=0.4, */*;q=0.5"
        self.assertEqual(1, quality("text/html;level=1", accept))
        self.assertEqual(0.7, quality("text/html", accept))
        self.assertEqual(0.3, quality("text/plain", accept))
        self.assertEqual(0.5, quality("image/jpeg", accept))
        self.assertEqual(0.4, quality("text/html;level=2", accept))
        self.assertEqual(0.7, quality("text/html;level=3", accept))

    def test_best_match(self):
        mime_types_supported = ['application/xbel+xml', 'application/xml']
        # direct match
        self.assertEqual(
            best_match(mime_types_supported, 'application/xbel+xml'),
            'application/xbel+xml')
        # direct match with a q parameter
        self.assertEqual(
            best_match(mime_types_supported, 'application/xbel+xml; q=1'),
            'application/xbel+xml')
        # direct match of our second choice with a q parameter
        self.assertEqual(
            best_match(mime_types_supported, 'application/xml; q=1'),
            'application/xml')
        # match using a subtype wildcard
        self.assertEqual(
            best_match(mime_types_supported, 'application/*; q=1'),
            'application/xml')
        # match using a type wildcard
        self.assertEqual(
            best_match(mime_types_supported, '*/*'), 'application/xml')

        mime_types_supported = ['application/xbel+xml', 'text/xml']
        # match using a type versus a lower weighted subtype
        self.assertEqual(
            best_match(mime_types_supported, 'text/*;q=0.5,*/*; q=0.1'),
            'text/xml')
        # fail to match anything
        self.assertEqual(
            best_match(mime_types_supported,
                       'text/html,application/atom+xml; q=0.9'), '')

        # common AJAX scenario
        mime_types_supported = ['application/json', 'text/html']
        self.assertEqual(
            best_match(mime_types_supported,
                       'application/json, text/javascript, */*'),
            'application/json')
        # verify fitness ordering
        self.assertEqual(
            best_match(mime_types_supported,
                       'application/json, text/html;q=0.9'),
            'application/json')

    def test_support_wildcards(self):
        mime_types_supported = ['image/*', 'application/xml']
        # match using a type wildcard
        self.assertEqual(
            best_match(mime_types_supported, 'image/png'), 'image/*')
        # match using a wildcard for both requested and supported
        self.assertEqual(best_match(mime_types_supported, 'image/*'),
                         'image/*')

    def test_best_match_many_slashes(self):
        """
        L{best_match} returns an emtpy string if the mime type contains
        multiple slashes.
        """
        self.assertEqual('', best_match(['application/json'],
                                        'application/json/parse'))

    def test_best_match_with_misplaced_semicolon(self):
        """
        L{best_match} returns an empty string if the MIME type contains a
        semicolon in an inappropriate spot.
        """
        # The semicolon after 'application/xml' doesn't conform to the MIME
        # type format.  It should be a comma.
        accept = 'text/html,application/xml;image/png,image/*;q=0.9,*/*;q=0.8'
        self.assertEqual('', best_match(['text/html'], accept))
