#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' Util module '

import os, re, time, base64, hashlib, logging, functools, mimetypes

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import Image
except ImportError:
    from PIL import Image

from transwarp.web import ctx, get, post, route, jsonrpc, Dict, Template, seeother, notfound, badrequest
from transwarp import db

import const

_REG_EMAIL = re.compile(r'^[0-9a-z]([\-\.\w]*[0-9a-z])*\@([0-9a-z][\-\w]*[0-9a-z]\.)+[a-z]{2,9}$')

_SESSION_COOKIE_NAME = '_auth_session_cookie'
_SESSION_COOKIE_KEY = '_SECURE_keyabc123xyz_BIND_'
_SESSION_COOKIE_EXPIRES = 31536000.0

def http_basic_auth(auth):
    try:
        s = base64.b64decode(auth)
        logging.warn(s)
        u, p = s.split(':', 1)
        user = db.select_one('select * from users where email=?', u)
        if user.passwd==hashlib.md5(p).hexdigest():
            logging.info('Basic auth ok: %s' % u)
            return user
        return None
    except BaseException, e:
        logging.exception('auth failed.')
        return None

def load_module(module_name):
    '''
    Load a module and return the module reference.
    '''
    pos = module_name.rfind('.')
    if pos==(-1):
        return __import__(module_name, globals(), locals(), [module_name])
    return __import__(module_name, globals(), locals(), [module_name[pos+1:]])

def scan_submodules(module_name):
    '''
    Scan sub modules and import as dict (key=module name, value=module).

    >>> ms = scan_submodules('apps')
    >>> type(ms['article'])
    <type 'module'>
    >>> ms['article'].__name__
    'apps.article'
    >>> type(ms['manage'])
    <type 'module'>
    >>> ms['manage'].__name__
    'apps.manage'
    '''
    web_root = os.path.dirname(os.path.abspath(__file__))
    mod_path = os.path.join(web_root, *module_name.split('.'))
    if not os.path.isdir(mod_path):
        raise IOError('No such file or directory: %s' % mod_path)
    dirs = os.listdir(mod_path)
    mod_dict = {}
    for name in dirs:
        if name=='__init__.py':
            continue
        p = os.path.join(mod_path, name)
        if os.path.isfile(p) and name.endswith('.py'):
            pyname = name[:-3]
            mod_dict[pyname] = __import__('%s.%s' % (module_name, pyname), globals(), locals(), [pyname])
        if os.path.isdir(p) and os.path.isfile(os.path.join(mod_path, name, '__init__.py')):
            mod_dict[name] = __import__('%s.%s' % (module_name, name), globals(), locals(), [name])
    return mod_dict

def _load_plugin_settings(plugin_type, provider_name, provider_cls):
    stored = get_settings(kind='%s.%s' % (plugin_type, provider_name), remove_prefix=True)
    settings = list(provider_cls.get_settings())
    for setting in settings:
        setting['value'] = stored.get(setting['key'], '')
    return settings, int(stored.get('order', 100000 + ord(provider_name[0]))), bool(stored.get('enabled', ''))

def save_plugin_settings(plugin_type, name, enabled, settings):
    provider = load_module('plugin.%s.%s' % (plugin_type, name)).Provider
    delete_settings('plugin.%s.%s' % (plugin_type, name))
    save_plugin_setting_enabled(plugin_type, name, enabled)
    for setting in provider.get_settings():
        key = setting['key']
        set_setting(name='%s.%s_%s' % (plugin_type, name, key), value=settings.get(key, ''))

def save_plugin_setting_enabled(plugin_type, name, enabled):
    set_setting(name='%s.%s_enabled' % (plugin_type, name), value='True' if enabled else '')

def create_signin_provider(name):
    provider = load_module('plugin.signin.%s' % name)
    settings = get_settings(kind='signin.%s' % name, remove_prefix=True)
    if settings['enabled']!='True':
        raise StandardError('Signin provider not enabled')
    return provider.Provider(**settings)

def create_upload_provider(name):
    provider = load_module('plugin.upload.%s' % name)
    return provider.Provider(**get_settings(kind='upload.%s' % name, remove_prefix=True))

def get_plugin_settings(plugin_type, name):
    provider = load_module('plugin.%s.%s' % (plugin_type, name)).Provider
    settings, order, enabled = _load_plugin_settings(plugin_type, name, provider)
    return settings, provider.get_description(), enabled

def order_plugin_providers(plugin_type, orders):
    providers = get_plugin_providers(plugin_type, names_only=True)
    n = 0
    for name in orders:
        if name in providers:
            set_setting(name='%s.%s_order' % (plugin_type, name), value=str(n))
            n = n + 1

def get_plugin_providers(plugin_type, names_only=False):
    '''
    Get plugin providers as list.
    '''
    ps = scan_submodules('plugin.%s' % plugin_type)
    if names_only:
        return ps.keys()
    providers = []
    for mod_name, mod in ps.iteritems():
        settings, order, enabled = _load_plugin_settings(plugin_type, mod_name, mod.Provider)
        provider = dict(name=mod.Provider.get_name(), description=mod.Provider.get_description(), settings=settings)
        provider['id'] = mod_name
        provider['order'] = order
        provider['enabled'] = enabled
        providers.append(provider)
    return sorted(providers, key=lambda p: p['order'])

def get_enabled_upload():
    '''
    Get selected upload plugin and return (name, Provider class), or (None, None) if no such setting.
    '''
    providers = [p for p in get_plugin_providers('upload') if p['enabled']]
    if providers:
        pid = providers[0]['id']
        try:
            return pid, load_module('plugin.upload.%s' % pid).Provider
        except ImportError:
            pass
    return None, None

def make_session_cookie(provider, uid, passwd, expires):
    '''
    Generate a secure client session cookie by constructing: 
    base64(uid, expires, md5(auth_provider, uid, expires, passwd, salt)).
    
    Args:
        auth_provider: auth provider.
        uid: user id.
        expires: unix-timestamp as float.
        passwd: user's password.
        salt: a secure string.
    Returns:
        base64 encoded cookie value as str.
    '''
    pvd = str(provider)
    sid = str(uid)
    exp = str(int(expires)) if expires else str(int(time.time() + 86400))
    secure = ':'.join([pvd, sid, exp, str(passwd), _SESSION_COOKIE_KEY])
    cvalue = ':'.join([pvd, sid, exp, hashlib.md5(secure).hexdigest()])
    logging.info('make cookie: %s' % cvalue)
    cookie = base64.urlsafe_b64encode(cvalue).replace('=', '_')
    ctx.response.set_cookie(_SESSION_COOKIE_NAME, cookie, expires=expires)

def extract_session_cookie():
    '''
    Decode a secure client session cookie and return uid, or None if invalid cookie.

    Returns:
        user id as str, or None if cookie is invalid.
    '''
    def _get_passwd_by_uid(provider, userid):
        if provider==const.LOCAL_SIGNIN_PROVIDER:
            return db.select_one('select passwd from users where id=?', userid).passwd
        return db.select_one('select auth_token from auth_users where user_id=? and provider=?', userid, provider).auth_token
    s = ctx.request.cookie(_SESSION_COOKIE_NAME, '')
    logging.info('read cookie: %s' % s)
    if not s:
        return None
    try:
        if isinstance(s, unicode):
            s = s.encode('utf-8')
        ss = base64.urlsafe_b64decode(s.replace('_', '=')).split(':')
        logging.info('decode cookie: %s' % str(ss))
        if len(ss)!=4:
            return None
        provider, uid, exp, md5 = ss
        if float(exp) < time.time():
            return None
        expected = ':'.join([provider, uid, exp, str(_get_passwd_by_uid(provider, uid)), _SESSION_COOKIE_KEY])
        if hashlib.md5(expected).hexdigest()!=md5:
            return None
        return uid
    except BaseException:
        return None

def delete_session_cookie():
    ' delete the session cookie immediately. '
    ctx.response.delete_cookie(_SESSION_COOKIE_NAME)

def get_menus():
    '''
    Get navigation menus as list, each element is a Dict object.
    '''
    menus = db.select('select * from menus order by display_order, name')
    if menus:
        return menus
    current = time.time()
    menu = Dict(id=db.next_str(), name=u'Home', description=u'', type='latest_articles', display_order=0, ref='', url='/latest', creation_time=current, modified_time=current, version=0)
    db.insert('menus', **menu)
    return [menu]

def delete_settings(kind):
    db.update('delete from settings where kind=?', kind)

def get_settings(kind=None, remove_prefix=False):
    '''
    Get all settings.
    '''
    settings = dict()
    if kind:
        L = db.select('select name, value from settings where kind=?', kind)
    else:
        L = db.select('select name, value from settings')
    for s in L:
        key = s.name[s.name.find('_')+1:] if remove_prefix else s.name
        settings[key] = s.value
    return settings

def get_setting(name, default=''):
    '''
    Get setting by name. Return default value '' if not exist.
    '''
    ss = db.select('select value from settings where name=?', name)
    if ss:
        v = ss[0].value
        if v:
            return v
    return default

def set_setting(name, value):
    '''
    Set setting by name and value.
    '''
    pos = name.find('_')
    if pos<=0:
        raise ValueError('bad setting name: %s must be xxx_xxx' % name)
    kind = name[:pos]
    current = time.time()
    if 0==db.update('update settings set value=?, modified_time=?, version=version+1 where name=?', value, current, name):
        st = dict(id=db.next_str(), kind=kind, name=name, value=value, creation_time=current, modified_time=current, version=0)
        db.insert('settings', **st)

def set_text(name, value):
    '''
    Set text by name and value.
    '''
    pos = name.find('_')
    if pos<=0:
        raise ValueError('bad setting name: %s must be xxx_xxx' % name)
    kind = name[:pos]
    current = time.time()
    if 0==db.update('update texts set value=?, modified_time=?, version=version+1 where name=?', value, current, name):
        st = dict(id=db.next_str(), kind=kind, name=name, value=value, creation_time=current, modified_time=current, version=0)
        db.insert('texts', **st)

def get_text(name, default=''):
    '''
    Get text by name. Return default value '' if not exist.
    '''
    ss = db.select('select value from texts where name=?', name)
    if ss:
        v = ss[0].value
        if v:
            return v
    return default

def get_setting_search_provider():
    return get_setting('search_provider', 'google')

def get_setting_site_name():
    return get_setting('site_name', 'iTranswarp')

def get_setting_site_description():
    return get_setting('site_description', '')

def get_active_theme():
    return get_setting('theme_active', 'default')

def set_active_theme(tid):
    for t in load_themes():
        if t.id==tid:
            set_setting('theme_active', tid)
            return

def load_themes():

    def _is_theme(root, name):
        p = os.path.join(root, name)
        return os.path.isdir(p) and os.path.isfile(os.path.join(p, '__init__.py'))

    def _get_theme_info(name):
        m = load_module('themes.%s' % name)
        return Dict( \
            id = name, \
            name = getattr(m, 'name', name), \
            description = getattr(m, 'description', '(no description)'), \
            author = getattr(m, 'author', '(unknown)'), \
            version = getattr(m, 'version', '1.0'), \
            snapshot = '/themes/%s/static/snapshot.png' % name)

    root = os.path.join(ctx.document_root, 'themes')
    subs = os.listdir(root)
    L = [_get_theme_info(p) for p in subs if _is_theme(root, p)]
    return sorted(L, lambda x, y: -1 if x.name.lower() < y.name.lower() else 1)

def _init_theme(path, model):
    theme = get_active_theme()
    model['__theme_path__'] = '/themes/%s' % theme
    model['__get_theme_path__'] = lambda _templpath: 'themes/%s/%s' % (theme, _templpath)
    model['__menus__'] = db.select('select * from menus order by display_order, name')
    model.update(get_settings('site'))
    if not 'site_name' in model:
        model['site_name'] = 'iTranswarp'
    if not '__title__' in model:
        model['__title__'] = model['site_name']
    model['ctx'] = ctx
    model['__layout_categories__'] = db.select('select * from categories order by display_order, name')
    return 'themes/%s/%s' % (theme, path), model

def theme(path):
    '''
    ThemeTemplate uses 'themes/<active-theme>' + template path to get real template.
    '''
    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kw):
            r = func(*args, **kw)
            if isinstance(r, dict):
                templ_path, model = _init_theme(path, r)
                return Template(templ_path, model)
            return r
        return _wrapper
    return _decorator

class ThemeTemplate(Template):
    '''
    ThemeTemplate uses 'themes/<active-theme>' + template path to get real template.
    '''
    def __init__(self, path, model=None, **kw):
        templ_path, m = _init_theme(path, r)
        super(ThemeTemplate, self).__init__(templ_path, m, **kw)

def make_comment(ref_type, ref_id, user, content):
    '''
    Make a comment.

    Args:
        ref_type: the ref type, e.g. 'article'.
        ref_id: the ref id, e.g., article id.
        user: current user.
        content: comment content.
    Returns:
        the comment object as dict.
    '''
    cid = db.next_str()
    kw = dict(id=cid, ref_type=ref_type, ref_id=ref_id, user_id=user.id, image_url=user.image_url, name=user.name, content=content, creation_time=time.time(), version=0)
    db.insert('comments', **kw)
    return kw

def get_comments_desc(ref_id, max_results=20, after_id=None):
    '''
    Get comments by page.

    Args:
        ref_id: reference id.
        max_results: the max results.
        after_id: comments after id.
    Returns:
        comments as list.
    '''
    if max_results < 1 or max_results > 100:
        raise ValueError('bad max_results')
    if after_id:
        return db.select('select * from comments where ref_id=? and id < ? order by id desc limit ?', ref_id, after_id, max_results)
    return db.select('select * from comments where ref_id=? order by id desc limit ?', ref_id, max_results)

def get_comments(ref_id, page_index=1, page_size=20):
    '''
    Get comments by page.

    Args:
        page_index: page index from 1.
        page_size: page size.
    Returns:
        comments as list, has_next as bool.
    '''
    if page_index < 1:
        raise ValueError('bad page_index')
    if page_size < 1 or page_size > 100:
        raise ValueError('bad page_size')
    offset = (page_index - 1) * page_size
    logging.warn('offset=%s, page_size=%s' % (offset, page_size))
    cs = db.select('select * from comments where ref_id=? order by creation_time desc limit ?,?', ref_id, offset, page_size + 1)
    logging.warn('len()=%s' % len(cs))
    if len(cs) > page_size:
        return cs[:page_size], True
    return cs, False

def upload_resource(ref_type, ref_id, fname, fp):
    ' upload resource and return resource object '
    uname, uprovider = get_enabled_upload()
    if uname is None:
        return dict(error=_('No uploader selected'))

    filename = os.path.split(fname)[1]
    if len(filename) > 50:
        filename = filename[-50:]
    ext = os.path.splitext(filename)[1].lower()
    mime = mimetypes.types_map.get(ext, 'application/octet-stream')
    current = time.time()
    fcontent = fp if isinstance(fp, str) else fp.read()

    m = dict( \
            id = db.next_str(), \
            ref_id = ref_id, \
            ref_type = ref_type, \
            deleted = False, \
            size = len(fcontent), \
            filename = filename, \
            mime = mime, \
            uploader = uname, \
            ref = '', \
            url = '', \
            creation_time = current, \
            modified_time = current, \
            version = 0 \
    )
    r = create_upload_provider(uname).upload(ref_type, ext, fcontent)
    for k in r:
        if k in m:
            m[k] = r[k]
    db.insert('resources', **m)
    return m

def create_thumbnail(fcontent, max_width=90, max_height=90):
    '''
    create thumbnail JPEG as str with size no more than max_width and max_height, and return dict contains:
    width,
    height,
    metadata,
    thumbnail.
    '''
    im = Image.open(StringIO(fcontent))
    w, h = im.size[0], im.size[1]
    meta = 'format=%s&mode=%s' % (im.format, im.mode)
    # calculate thumbnail width, height:
    tw = max_width
    th = tw * h / w
    if th > max_height:
        th = max_height
        tw = th * w / h
    if tw < 5:
        tw = 5
    if th < 5:
        th = 5
    im.thumbnail((tw, th), Image.ANTIALIAS)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    return dict(width=w, height=h, metadata=meta, thumbnail=im.tostring('jpeg', 'RGB'))

def delete_resources(ref_type, ref_id):
    db.update_kw('resources', 'ref_id=?', ref_id, deleted=True)

def validate_email(email):
    '''
    Validate email address. Make sure email is lowercase.

    >>> validate_email('michael@example.com')
    True
    >>> validate_email(u'michael.liao@example.com.cn')
    True
    >>> validate_email('michael-liao@staff.example-inc.com.hk')
    True
    >>> validate_email('007michael@staff.007.com.cn')
    True
    >>> validate_email('localhost')
    False
    >>> validate_email('@localhost')
    False
    >>> validate_email('michael@')
    False
    >>> validate_email('michael@localhost')
    False
    >>> validate_email('michael@local.host.')
    False
    >>> validate_email('-hello@example.local')
    False
    >>> validate_email('michael$name@local.local')
    False
    >>> validate_email('user.@example.com')
    False
    >>> validate_email('user-@example.com')
    False
    >>> validate_email('user-0@example-.com')
    False
    '''
    m = _REG_EMAIL.match(str(email))
    return not m is None

if __name__=='__main__':
    import doctest
    doctest.testmod()
 