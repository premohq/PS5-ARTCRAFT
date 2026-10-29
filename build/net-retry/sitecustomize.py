"""Retries for the build's downloads, loaded by every Python in the build container (site imports sitecustomize).

The fork's tools fetch their pinned inputs with urllib.request.urlopen, once each; over a build of hours one dropped
connection (a reset, a timeout, a 5xx) was enough to lose the run. This wraps urlopen: it reads the whole response
inside the retry, so a connection that drops mid-body is retried too, and hands back the body in memory. An HTTP
error other than 408, 429 or 5xx is raised at once, as before.
"""
import http.client
import io
import socket
import sys
import time
import urllib.error
import urllib.request

_urlopen = urllib.request.urlopen
_TRIES, _RETRY_STATUS = 6, {408, 425, 429, 500, 502, 503, 504}


class _Body(io.BytesIO):
    """The response, read: what callers use of http.client.HTTPResponse."""

    def __init__(self, data, response):
        super().__init__(data)
        self.status = self.code = response.status
        self.reason, self.headers, self.url = response.reason, response.headers, response.geturl()
        self.msg = response.headers

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def info(self):
        return self.headers

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def getheaders(self):
        return list(self.headers.items())


def urlopen(url, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *args, **kwargs):
    for attempt in range(1, _TRIES + 1):
        try:
            with _urlopen(url, data, timeout, *args, **kwargs) as response:
                return _Body(response.read(), response)
        except urllib.error.HTTPError as error:
            if error.code not in _RETRY_STATUS or attempt == _TRIES:
                raise
            reason = f'HTTP {error.code}'
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError, socket.timeout) as error:
            if attempt == _TRIES:
                raise
            reason = repr(error)
        wait = min(60, 5 * 2 ** (attempt - 1))
        target = url.full_url if isinstance(url, urllib.request.Request) else url
        print(f'urlopen {target}: {reason}; try {attempt + 1} of {_TRIES} in {wait} s', file=sys.stderr)
        time.sleep(wait)


urllib.request.urlopen = urlopen
