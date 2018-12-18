import logging
import pkg_resources
import socket
import threading
import time

from .. import listen
from .. import voeventclient
from ..handlers import include_notice_types

# Set up logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

payloads = [pkg_resources.resource_string(__name__, 'data/gbm_flt_pos.xml'),
            pkg_resources.resource_string(__name__, 'data/kill_socket.xml')]


def serve(payloads, host='127.0.0.1', port=8099, retransmit_timeout=0,
          log=None):
    """Rudimentary GCN server, for testing purposes. Serves just one connection
    at a time, and repeats the same payloads in order, repeating, for each
    connection."""
    if log is None:
        log = logging.getLogger('gcn.serve')

    sock = socket.socket()
    try:
        sock.bind((host, port))
        log.info("test server bound to %s:%d", host, port)
        sock.listen(5)
        for i in range(5):
            conn, addr = sock.accept()
            log.info("connected to %s:%d", addr, port)
            try:
                for payload in payloads:
                    time.sleep(retransmit_timeout)
                    voeventclient._send_packet(conn, payload)
            except socket.error:
                log.exception('error communicating with peer')
            finally:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except socket.error:
                    log.exception("could not shut down socket")

                try:
                    conn.close()
                except socket.error:
                    log.exception("could not close socket")
                else:
                    log.info("closed socket")
    finally:
        sock.close()


class MessageCounter(object):

    def __init__(self):
        self.count = 0

    def __call__(self, *args):
        self.count += 1


def test_reconnect_after_kill():
    """Test that the client recovers if the server closes the connection."""

    time.sleep(5)

    server_thread = threading.Thread(
        group=None, target=serve, args=(payloads,),
        kwargs=dict(retransmit_timeout=0.1))
    server_thread.daemon = True
    server_thread.start()

    handler = MessageCounter()

    # FIXME: workaround for https://bugs.python.org/issue3445,
    # fixed in Python 3.3
    handler.__name__ = ''

    logger = logging.getLogger()

    client_thread = threading.Thread(
        group=None, target=listen,
        kwargs=dict(host='127.0.0.1',
                    max_reconnect_timeout=4,
                    handler=include_notice_types(111)(handler),
                    log=logger,
                    )
        )
    client_thread.daemon = True
    client_thread.start()

    time.sleep(5)
    assert handler.count == 5
