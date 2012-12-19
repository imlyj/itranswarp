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

import os, logging
logging.basicConfig(level=logging.INFO)

from transwarp import i18n; i18n.install_i18n(); i18n.load_i18n('i18n/zh_cn.txt')
from transwarp import web, db, cache

from plugin.filters import load_user, load_i18n

from conf.mysql import DB_SCHEMA, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD

def create_app():
    cache.client = cache.RedisClient('localhost')
    db.init(db_type = 'mysql', \
            db_schema = DB_SCHEMA, \
            db_host = DB_HOST, \
            db_port = DB_PORT, \
            db_user = DB_USER, \
            db_password = DB_PASSWORD, \
            use_unicode = True, charset = 'utf8')
    return web.WSGIApplication(('static_handler', 'install', 'admin', 'apps.manage', 'apps.article', 'apps.photo'), \
            document_root=os.path.dirname(os.path.abspath(__file__)), \
            filters=(load_user, load_i18n), template_engine='jinja2', \
            DEBUG=True)

if __name__=='__main__':
    logging.info('application will start...')
    server = make_server('127.0.0.1', 8080, create_app())
    server.serve_forever()
