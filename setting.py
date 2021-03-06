#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Setting module that store settings in database, do not check permissions. '

import time, base64, logging

from transwarp.web import ctx
from transwarp import db, cache

_GLOBAL = '__global__'

def set_text(kind, key, value):
    '''
    Set text by kind, key and value.
    '''
    if len(kind)==0 or len(kind)>50 or len(key)==0 or len(key)>50:
        raise ValueError('invalid setting name.')
    if not isinstance(value, (str, unicode)):
        value = str(value)
    name = '%s:%s' % (kind, key)
    text = dict( \
        id = db.next_str(), \
        website_id = ctx.website.id, \
        kind = kind, \
        name = name, \
        value = value, \
        creation_time = time.time(), \
        version = 0)
    db.update('delete from texts where name=? and website_id=?', name, ctx.website.id)
    db.insert('texts', **text)
    cache.client.delete('TEXT:%s:%s:%s' % (ctx.website.id, kind, key))

def _get_text(website_id, kind, key, default):
    ss = db.select('select value from texts where name=? and website_id=?', '%s:%s' % (kind, key), website_id)
    if ss:
        v = ss[0].value
        if v:
            return v
    return default

def get_text(kind, key, default=u''):
    '''
    Get text by kind and key. Return default value u'' if not exist.
    '''
    cache_key = 'TEXT:%s:%s:%s' % (ctx.website.id, kind, key)
    r = cache.client.get(cache_key)
    if r is not None:
        return r
    r = _get_text(ctx.website.id, kind, key, default)
    cache.client.set(cache_key, r, 3600)
    return r

def _get_setting(website_id, kind, key, default=u''):
    ss = db.select('select value from settings where name=? and website_id=?', '%s:%s' % (kind, key), website_id)
    if ss:
        v = ss[0].value
        if v:
            return v
    return default

def get_setting(kind, key, default=u''):
    '''
    Get setting by kind and key. Return default value u'' if not exist.
    '''
    return _get_setting(ctx.website.id, kind, key, default)

def get_global_setting(kind, key, default=u''):
    return _get_setting(_GLOBAL, kind, key, default)

def _get_settings(website_id, kind, removePrefix=True):
    '''
    Return key, value as dict.
    '''
    L = db.select('select name, value from settings where kind=? and website_id=?', kind, website_id)
    d = {}
    if removePrefix:
        l = len(kind) + 1
        for s in L:
            d[s.name[l:]] = s.value
    else:
        for s in L:
            d[s.name] = s.value
    return d

def get_settings(kind, removePrefix=True):
    return _get_settings(ctx.website.id, kind, removePrefix)

def get_global_settings(kind, removePrefix=True):
    return _get_settings(_GLOBAL, kind, removePrefix)

def _set_setting(website_id, kind, key, value):
    '''
    Set setting by kind, key and value.
    '''
    if len(kind)==0 or len(kind)>50 or len(key)==0 or len(key)>50:
        raise ValueError('invalid setting name.')
    if not isinstance(value, (str, unicode)):
        value = str(value)
    name = '%s:%s' % (kind, key)
    settings = dict( \
        id = db.next_str(), \
        website_id = website_id, \
        kind = kind, \
        name = name, \
        value = value, \
        creation_time = time.time(), \
        version = 0)
    db.update('delete from settings where name=? and website_id=?', name, website_id)
    db.insert('settings', **settings)

def set_setting(kind, key, value):
    _set_setting(ctx.website.id, kind, key, value)

def set_global_setting(kind, key, value):
    _set_setting(_GLOBAL, kind, key, value)

@db.with_transaction
def _set_settings(website_id, kind, **kw):
    '''
    set settings by kind and key-value pair.
    '''
    for k, v in kw.iteritems():
        _set_setting(website_id, kind, k, v)

def set_settings(kind, **kw):
    _set_settings(ctx.website.id, kind, **kw)

def set_global_settings(kind, **kw):
    _set_settings(_GLOBAL, kind, **kw)

def _delete_setting(website_id, kind, key):
    name = '%s:%s' % (kind, key)
    db.update('delete from settings where name=? and website_id=?', name, website_id)

def delete_setting(kind, key):
    _delete_setting(ctx.website.id, kind, key)

def delete_global_setting(kind, key):
    _delete_setting(_GLOBAL, kind, key)

def _delete_settings(website_id, kind):
    db.update('delete from settings where kind=? and website_id=?', kind, website_id)

def delete_settings(kind):
    _delete_settings(ctx.website.id, kind)

KIND_WEBSITE = 'website'

WEBSITE_DESCRIPTION = 'description'
WEBSITE_COPYRIGHT = 'copyright'
WEBSITE_TIMEZONE = 'timezone'
WEBSITE_DATE_FORMAT = 'dateformat'
WEBSITE_TIME_FORMAT = 'timeformat'
WEBSITE_DATETIME_FORMAT = 'datetimeformat'

KEYS_WEBSITE = set([WEBSITE_DESCRIPTION, WEBSITE_COPYRIGHT, WEBSITE_TIMEZONE, WEBSITE_DATE_FORMAT, WEBSITE_TIME_FORMAT])

DATE_FORMATS = [
    u'%B %d, %Y',
    u'%a, %b %d, %Y',
    u'%b %d, %Y',
    u'%m/%d/%Y',
    u'%d/%m/%Y',
    u'%Y-%m-%d',
    u'%y-%m-%d',
]

TIME_FORMATS = [
    u'%H:%M:%S',
    u'%H:%M',
    u'%I:%M %p',
]

DEFAULT_TIMEZONE = u'+00:00'
TIMEZONES = [
    u'-12:00',
    u'-11:00',
    u'-10:00',
    u'-09:30',
    u'-09:00',
    u'-08:00',
    u'-07:00',
    u'-06:00',
    u'-05:00',
    u'-04:30',
    u'-04:00',
    u'-03:30',
    u'-03:00',
    u'-02:00',
    u'-01:00',
    DEFAULT_TIMEZONE,
    u'+01:00',
    u'+02:00',
    u'+03:00',
    u'+03:30',
    u'+04:00',
    u'+04:30',
    u'+05:00',
    u'+05:30',
    u'+05:45',
    u'+06:00',
    u'+06:30',
    u'+07:00',
    u'+08:00',
    u'+09:00',
    u'+09:30',
    u'+10:00',
    u'+10:30',
    u'+11:00',
    u'+11:30',
    u'+12:00',
    u'+12:45',
    u'+13:00',
    u'+14:00',
]

def get_website_settings():
    d = get_settings(KIND_WEBSITE)
    if not WEBSITE_DESCRIPTION in d:
        d[WEBSITE_DESCRIPTION] = u''
    if not WEBSITE_COPYRIGHT in d:
        d[WEBSITE_COPYRIGHT] = u''
    if not WEBSITE_TIMEZONE in d:
        d[WEBSITE_TIMEZONE] = DEFAULT_TIMEZONE
    if not WEBSITE_DATE_FORMAT in d:
        d[WEBSITE_DATE_FORMAT] = DATE_FORMATS[0]
    if not WEBSITE_TIME_FORMAT in d:
        d[WEBSITE_TIME_FORMAT] = TIME_FORMATS[0]
    d[WEBSITE_DATETIME_FORMAT] = u'%s %s' % (d[WEBSITE_DATE_FORMAT], d[WEBSITE_TIME_FORMAT])
    return d

def set_website_settings(**kw):
    d = {}
    for k, v in kw.iteritems():
        if k in KEYS_WEBSITE:
            d[k] = v
    set_settings(KIND_WEBSITE, **d)
    return d

KIND_SMTP = 'smtp'
SMTP_HOST = 'host'
SMTP_PORT = 'port'
SMTP_USE_TLS = 'use_tls'
SMTP_USERNAME = 'username'
SMTP_PASSWD = 'passwd'
SMTP_FROM_ADDR = 'from_addr'

KEYS_SMTP = set([SMTP_HOST, SMTP_PORT, SMTP_USE_TLS, SMTP_USERNAME, SMTP_PASSWD, SMTP_FROM_ADDR])

def get_smtp_settings():
    d = get_global_settings(KIND_SMTP)
    if not SMTP_HOST in d:
        d[SMTP_HOST] = u'localhost'
    if not SMTP_PORT in d:
        d[SMTP_PORT] = u'0'
    if not SMTP_USE_TLS in d:
        d[SMTP_USE_TLS] = u''
    if not SMTP_USERNAME in d:
        d[SMTP_USERNAME] = u''
    if not SMTP_PASSWD in d:
        d[SMTP_PASSWD] = u''
    if not SMTP_FROM_ADDR in d:
        d[SMTP_FROM_ADDR] = u''
    return d

def set_smtp_settings(**kw):
    d = {}
    for k, v in kw.iteritems():
        if k in KEYS_SMTP:
            d[k] = v
    set_global_settings(KIND_SMTP, **d)
    return d

if __name__=='__main__':
    import doctest
    doctest.testmod()
 