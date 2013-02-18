#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
A WSGI app for DEV ONLY.

Commands for init mysql db:

> create database itranswarp;
> create user 'www-data'@'localhost' identified by 'www-data';
> grant all privileges on itranswarp.* to 'www-data'@'localhost' identified by 'www-data';

or for production mode:

> grant select,insert,update,delete on itranswarp.* to 'www-data'@'localhost' identified by 'www-data';
'''

from wsgiref.simple_server import make_server

import os
import logging; logging.basicConfig(level=logging.DEBUG)
import locale; locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

from transwarp import i18n; i18n.install_i18n(); i18n.load_i18n('i18n/zh_cn.txt')
from transwarp import web, db, cache

from loader import load_site, load_user, load_i18n

def create_app():
    cache.client = cache.RedisClient('localhost')
    db.init(db_type = 'mysql', \
            db_schema = 'itranswarp', \
            db_host = 'localhost', \
            db_port = 3306, \
            db_user = 'root', \
            db_password = 'passw0rd', \
            use_unicode = True, charset = 'utf8')
    return web.WSGIApplication(('apps.article', 'apps.website', 'static_handler', 'install', 'auth', 'admin',), \
            document_root=os.path.dirname(os.path.abspath(__file__)), \
            filters=(load_site, load_user, load_i18n), template_engine='jinja2', \
            DEBUG=True)

if __name__=='__main__':
    logging.info('application will start...')
    server = make_server('127.0.0.1', 8080, create_app())
    server.serve_forever()
