#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' parse html and generate summary '

import re, logging

from HTMLParser import HTMLParser
from htmlentitydefs import name2codepoint

import markdown2

class MyHTMLParser(HTMLParser):

    def __init__(self):
        HTMLParser.__init__(self)
        self._tag_stack = []
        self._buffer = []
        self._length = 0
        self._last_is_pre = False

    def enough(self, length):
        return self._length >= length

    def flush(self):
        ' Return html as unicode '
        L = []
        L.extend(self._buffer)
        for s in reversed(self._tag_stack):
            L.append(u'</%s>' % s)
        return u''.join(L)

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        self._last_is_pre = tag=='pre'
        if attrs:
            self._buffer.append(u'<%s %s>' % (tag, u' '.join([u'%s="%s"' % (k, v) for k, v in attrs])))
        else:
            self._buffer.append(u'<%s>' % tag)

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1]==tag:
            self._tag_stack.pop()
            self._buffer.append(u'</%s>' % tag)
            self._last_is_pre = False
        else:
            logging.warn('ERROR when parsing tag.')

    def handle_startendtag(self, tag, attrs):
        if tag=='br' or tag=='hr' or tag=='img':
            if attrs:
                self._buffer.append(u'<%s %s />' % (tag, u' '.join([u'%s="%s"' % (k, v) for k, v in attrs])))
            else:
                self._buffer.append(u'<%s />' % tag)
            self._last_is_pre = False
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_data(self, data):
        s = data if self._last_is_pre else data.strip()
        self._length = self._length + len(s)
        self._buffer.append(s)

    def handle_comment(self, data):
        pass

    def handle_entityref(self, name):
        self._length = self._length + 1
        self._buffer.append(u'&%s;' % name)

    def handle_charref(self, name):
        self._length = self._length + 1
        self._buffer.append(u'&#%s;' % name)

_RE_END_PARA = re.compile(ur'(\<\/)(p)|(div)|(pre)(\>)')

def to_html(obj):
    return markdown2.markdown(obj.content)

def parse(s, maxchars):
    L = _RE_END_PARA.split(s)
    parser = MyHTMLParser()
    summary = None
    for s in L:
        if s:
            parser.feed(s)
        if not summary and parser.enough(maxchars):
            summary = parser.flush()
    h = parser.flush()
    if not summary:
        summary = h
    return h, summary

def parse_md(s, maxchars):
    h = markdown2.markdown(s)
    return parse(h, maxchars)

if __name__=='__main__':
    s = u'<p>paragrah 1</p> <pre>hello, <span>world</span>!</pre> <p color=red><a>another papa</a></p> <br/> <img src="test.jpg" /> <div>END</div><h1>END</h1>'
    print parse(s, 12)
    print parse_md(u'*Hello, 你好！*', 12)
    print markdown2.markdown('*hello, world!')
