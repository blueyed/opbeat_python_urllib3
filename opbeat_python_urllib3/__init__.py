# -*- coding: utf-8 -*-
import urllib3
from urllib3.exceptions import MaxRetryError, TimeoutError

try:
    import certifi
    ca_certs = certifi.where()
except ImportError:
    ca_certs = None


from opbeat.conf import defaults
from opbeat.transport.base import TransportException
from opbeat.transport.http import AsyncHTTPTransport, HTTPTransport


class Urllib3Transport(HTTPTransport):

    scheme = ['http', 'https']
    http = urllib3.PoolManager(
        cert_reqs='CERT_REQUIRED' if ca_certs else 'CERT_NONE',
        ca_certs=ca_certs,
    )

    def send(self, data, headers, timeout=None):
        if timeout is None:
            timeout = defaults.TIMEOUT
        response = None
        try:
            try:
                response = self.http.urlopen(
                    'POST', self._url, body=data, headers=headers, timeout=timeout
                )
            except Exception as e:
                print_trace = True
                if isinstance(e, MaxRetryError) and isinstance(e.reason, TimeoutError):
                    message = (
                        "Connection to Opbeat server timed out "
                        "(url: %s, timeout: %d seconds)" % (self._url, timeout)
                    )
                    print_trace = False
                else:
                    message = 'Unable to reach Opbeat server: %s (url: %s)' % (
                        e, self._url
                    )
                raise TransportException(message, data, print_trace=print_trace)
            body = response.read()
            if response.status >= 400:
                if response.status == 429:  # rate-limited
                    message = 'Temporarily rate limited: '
                    print_trace = False
                else:
                    message = 'HTTP %s: ' % response.status
                    print_trace = True
                message += body.decode('utf8')
                raise TransportException(message, data, print_trace=print_trace)
            return response.getheader('Location')
        finally:
            if response:
                response.close()


class AsyncUrllib3Transport(AsyncHTTPTransport, Urllib3Transport):
    scheme = ['http', 'https']
    async_mode = True

    def send_sync(self, data=None, headers=None, success_callback=None,
                  fail_callback=None):
        try:
            url = Urllib3Transport.send(self, data, headers)
            if callable(success_callback):
                success_callback(url=url)
        except Exception as e:
            if callable(fail_callback):
                fail_callback(exception=e)
