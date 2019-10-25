import unittest
from phoenixdb.avatica import parse_url, urlparse


class ParseUrlTest(unittest.TestCase):

    def test_parse_url(self):
        self.assertEqual(urlparse.urlparse('http://localhost:8765/'), parse_url('localhost'))
        self.assertEqual(urlparse.urlparse('http://localhost:2222/'), parse_url('localhost:2222'))
        self.assertEqual(urlparse.urlparse('http://localhost:2222/'), parse_url('http://localhost:2222/'))
