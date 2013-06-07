# Copyright 2011-2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, self.list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, self.list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

from urllib2 import quote, unquote
from urlparse import urlparse
from threading import Thread
from json import dumps, loads
from time import time
from httplib import ResponseNotReady
from time import sleep
from random import random
from logging import getLogger

from objpool.http import PooledHTTPConnection


TIMEOUT = 60.0   # seconds
HTTP_METHODS = ['GET', 'POST', 'PUT', 'HEAD', 'DELETE', 'COPY', 'MOVE']

log = getLogger(__name__)
sendlog = getLogger('%s.send' % __name__)
recvlog = getLogger('%s.recv' % __name__)


def _encode(v):
    if v and isinstance(v, unicode):
        return quote(v.encode('utf-8'))
    return v


class ClientError(Exception):
    def __init__(self, message, status=0, details=None):
        log.debug('ClientError: msg[%s], sts[%s], dtl[%s]' % (
            message,
            status,
            details))
        try:
            message += '' if message and message[-1] == '\n' else '\n'
            serv_stat, sep, new_msg = message.partition('{')
            new_msg = sep + new_msg[:-1 if new_msg.endswith('\n') else 0]
            json_msg = loads(new_msg)
            key = json_msg.keys()[0]
            serv_stat = serv_stat.strip()

            json_msg = json_msg[key]
            message = '%s %s (%s)\n' % (
                serv_stat,
                key,
                json_msg['message']) if (
                    'message' in json_msg) else '%s %s' % (serv_stat, key)
            status = json_msg.get('code', status)
            if 'details' in json_msg:
                if not details:
                    details = []
                if not isinstance(details, list):
                    details = [details]
                if json_msg['details']:
                    details.append(json_msg['details'])
        except Exception:
            pass
        finally:
            while message.endswith('\n\n'):
                message = message[:-1]
            super(ClientError, self).__init__(message)
            self.status = status if isinstance(status, int) else 0
            self.details = details if details else []


class Logged(object):

    LOG_TOKEN = False
    LOG_DATA = False


class RequestManager(Logged):
    """Handle http request information"""

    def _connection_info(self, url, path, params={}):
        """ Set self.url to scheme://netloc/?params
        :param url: (str or unicode) The service url

        :param path: (str or unicode) The service path (url/path)

        :param params: (dict) Parameters to add to final url

        :returns: (scheme, netloc)
        """
        url = _encode(str(url)) if url else 'http://127.0.0.1/'
        url += '' if url.endswith('/') else '/'
        if path:
            url += _encode(path[1:] if path.startswith('/') else path)
        delim = '?'
        for key, val in params.items():
            val = _encode(val)
            url += '%s%s%s' % (delim, key, ('=%s' % val) if val else '')
            delim = '&'
        parsed = urlparse(url)
        self.url = url
        self.path = parsed.path or '/'
        if parsed.query:
            self.path += '?%s' % parsed.query
        return (parsed.scheme, parsed.netloc)

    def __init__(
            self, method, url, path,
            data=None, headers={}, params={}):
        method = method.upper()
        assert method in HTTP_METHODS, 'Invalid http method %s' % method
        if headers:
            assert isinstance(headers, dict)
        self.headers = dict(headers)
        self.method, self.data = method, data
        self.scheme, self.netloc = self._connection_info(url, path, params)

    def dump_log(self):
        sendlog.info('%s %s://%s%s\t[%s]' % (
            self.method, self.scheme, self.netloc, self.path, self))
        for key, val in self.headers.items():
            if (not self.LOG_TOKEN) and key.lower() == 'x-auth-token':
                continue
            sendlog.info('  %s: %s\t[%s]' % (key, val, self))
        if self.data:
            sendlog.info('data size:%s\t[%s]' % (len(self.data), self))
            if self.LOG_DATA:
                sendlog.info(self.data)
        else:
            sendlog.info('data size:0\t[%s]' % self)
        sendlog.info('')

    def perform(self, conn):
        """
        :param conn: (httplib connection object)

        :returns: (HTTPResponse)
        """
        conn.request(
            method=str(self.method.upper()),
            url=str(self.path),
            headers=self.headers,
            body=self.data)
        self.dump_log()
        keep_trying = TIMEOUT
        while keep_trying > 0:
            try:
                return conn.getresponse()
            except ResponseNotReady:
                wait = 0.03 * random()
                sleep(wait)
                keep_trying -= wait
        logmsg = 'Kamaki Timeout %s %s\t[%s]' % (self.method, self.path, self)
        recvlog.debug(logmsg)
        raise ClientError('HTTPResponse takes too long - kamaki timeout')


class ResponseManager(Logged):
    """Manage the http request and handle the response data, headers, etc."""

    def __init__(self, request, poolsize=None):
        """
        :param request: (RequestManager)
        """
        self.request = request
        self._request_performed = False
        self.poolsize = poolsize

    def _get_response(self):
        if self._request_performed:
            return

        pool_kw = dict(size=self.poolsize) if self.poolsize else dict()
        try:
            with PooledHTTPConnection(
                    self.request.netloc, self.request.scheme,
                    **pool_kw) as connection:
                self.request.LOG_TOKEN = self.LOG_TOKEN
                self.request.LOG_DATA = self.LOG_DATA
                r = self.request.perform(connection)
                recvlog.info('\n%s <-- %s <-- [req: %s]\n' % (
                    self, r, self.request))
                self._request_performed = True
                self._status_code, self._status = r.status, unquote(r.reason)
                recvlog.info(
                    '%d %s\t[p: %s]' % (self.status_code, self.status, self))
                self._headers = dict()
                for k, v in r.getheaders():
                    if (not self.LOG_TOKEN) and k.lower() == 'x-auth-token':
                        continue
                    v = unquote(v)
                    self._headers[k] = v
                    recvlog.info('  %s: %s\t[p: %s]' % (k, v, self))
                self._content = r.read()
                recvlog.info('data size: %s\t[p: %s]' % (
                    len(self._content) if self._content else 0,
                    self))
                if self.LOG_DATA and self._content:
                    recvlog.info('%s\t[p: %s]' % (self._content, self))
        except Exception as err:
            from traceback import format_stack
            recvlog.debug('\n'.join(['%s' % type(err)] + format_stack()))
            raise ClientError(
                'Failed while http-connecting to %s (%s)' % (
                    self.request.url,
                    err))

    @property
    def status_code(self):
        self._get_response()
        return self._status_code

    @property
    def status(self):
        self._get_response()
        return self._status

    @property
    def headers(self):
        self._get_response()
        return self._headers

    @property
    def content(self):
        self._get_response()
        return self._content

    @property
    def text(self):
        """
        :returns: (str) content
        """
        self._get_response()
        return '%s' % self._content

    @property
    def json(self):
        """
        :returns: (dict) squeezed from json-formated content
        """
        self._get_response()
        try:
            return loads(self._content)
        except ValueError as err:
            raise ClientError('Response not formated in JSON - %s' % err)


class SilentEvent(Thread):
    """Thread-run method(*args, **kwargs)"""
    def __init__(self, method, *args, **kwargs):
        super(self.__class__, self).__init__()
        self.method = method
        self.args = args
        self.kwargs = kwargs

    @property
    def exception(self):
        return getattr(self, '_exception', False)

    @property
    def value(self):
        return getattr(self, '_value', None)

    def run(self):
        try:
            self._value = self.method(*(self.args), **(self.kwargs))
        except Exception as e:
            recvlog.debug('Thread %s got exception %s\n<%s %s' % (
                self,
                type(e),
                e.status if isinstance(e, ClientError) else '',
                e))
            self._exception = e


class Client(object):

    MAX_THREADS = 7
    DATE_FORMATS = [
        '%a %b %d %H:%M:%S %Y',
        '%A, %d-%b-%y %H:%M:%S GMT',
        '%a, %d %b %Y %H:%M:%S GMT']
    LOG_TOKEN = False
    LOG_DATA = False

    def __init__(self, base_url, token):
        assert base_url, 'No base_url for client %s' % self
        self.base_url = base_url
        self.token = token
        self.headers, self.params = dict(), dict()

    def _init_thread_limit(self, limit=1):
        assert isinstance(limit, int) and limit > 0, 'Thread limit not a +int'
        self._thread_limit = limit
        self._elapsed_old = 0.0
        self._elapsed_new = 0.0

    def _watch_thread_limit(self, threadlist):
        self._thread_limit = getattr(self, '_thread_limit', 1)
        self._elapsed_new = getattr(self, '_elapsed_new', 0.0)
        self._elapsed_old = getattr(self, '_elapsed_old', 0.0)
        recvlog.debug('# running threads: %s' % len(threadlist))
        if self._elapsed_old and self._elapsed_old >= self._elapsed_new and (
                self._thread_limit < self.MAX_THREADS):
            self._thread_limit += 1
        elif self._elapsed_old <= self._elapsed_new and self._thread_limit > 1:
            self._thread_limit -= 1

        self._elapsed_old = self._elapsed_new
        if len(threadlist) >= self._thread_limit:
            self._elapsed_new = 0.0
            for thread in threadlist:
                begin_time = time()
                thread.join()
                self._elapsed_new += time() - begin_time
            self._elapsed_new = self._elapsed_new / len(threadlist)
            return []
        return threadlist

    def _raise_for_status(self, r):
        log.debug('raise err from [%s] of type[%s]' % (r, type(r)))
        status_msg = getattr(r, 'status', None) or ''
        try:
            message = '%s %s\n' % (status_msg, r.text)
        except:
            message = '%s %s\n' % (status_msg, r)
        status = getattr(r, 'status_code', getattr(r, 'status', 0))
        raise ClientError(message, status=status)

    def set_header(self, name, value, iff=True):
        """Set a header 'name':'value'"""
        if value is not None and iff:
            self.headers[name] = unicode(value)

    def set_param(self, name, value=None, iff=True):
        if iff:
            self.params[name] = unicode(value)

    def request(
            self, method, path,
            async_headers=dict(), async_params=dict(),
            **kwargs):
        """Commit an HTTP request to base_url/path
        Requests are commited to and performed by Request/ResponseManager
        These classes perform a lazy http request. Present method, by default,
        enforces them to perform the http call. Hint: call present method with
        success=None to get a non-performed ResponseManager object.
        """
        assert isinstance(method, str) or isinstance(method, unicode)
        assert method
        assert isinstance(path, str) or isinstance(path, unicode)
        try:
            headers = dict(self.headers)
            headers.update(async_headers)
            params = dict(self.params)
            params.update(async_params)
            success = kwargs.pop('success', 200)
            data = kwargs.pop('data', None)
            headers.setdefault('X-Auth-Token', self.token)
            if 'json' in kwargs:
                data = dumps(kwargs.pop('json'))
                headers.setdefault('Content-Type', 'application/json')
            if data:
                headers.setdefault('Content-Length', '%s' % len(data))

            sendlog.debug('\n\nCMT %s@%s\t[%s]', method, self.base_url, self)
            req = RequestManager(
                method, self.base_url, path,
                data=data, headers=headers, params=params)
            #  req.log()
            r = ResponseManager(req)
            r.LOG_TOKEN, r.LOG_DATA = self.LOG_TOKEN, self.LOG_DATA
        finally:
            self.headers = dict()
            self.params = dict()

        if success is not None:
            # Success can either be an int or a collection
            success = (success,) if isinstance(success, int) else success
            if r.status_code not in success:
                self._raise_for_status(r)
        return r

    def delete(self, path, **kwargs):
        return self.request('delete', path, **kwargs)

    def get(self, path, **kwargs):
        return self.request('get', path, **kwargs)

    def head(self, path, **kwargs):
        return self.request('head', path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('post', path, **kwargs)

    def put(self, path, **kwargs):
        return self.request('put', path, **kwargs)

    def copy(self, path, **kwargs):
        return self.request('copy', path, **kwargs)

    def move(self, path, **kwargs):
        return self.request('move', path, **kwargs)
