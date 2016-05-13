#!/usr/bin/python

# Copyright (c) 2016 IBM Corp.
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import socket
import threading


def daemonize():
    # A really basic daemonize method that should work well enough for
    # now in this circumstance. Based on the public domain code at:
    # http://web.archive.org/web/20131017130434/http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

    pid = os.fork()
    if pid > 0:
        return True

    os.chdir('/')
    os.setsid()
    os.umask(0)

    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    sys.stdout.flush()
    sys.stderr.flush()
    i = open('/dev/null', 'r')
    o = open('/dev/null', 'a+')
    e = open('/dev/null', 'a+', 0)
    os.dup2(i.fileno(), sys.stdin.fileno())
    os.dup2(o.fileno(), sys.stdout.fileno())
    os.dup2(e.fileno(), sys.stderr.fileno())
    return False


class Console(object):
    def __init__(self, path):
        self.path = path
        self.file = open(path)
        self.stat = os.stat(path)
        self.size = self.stat.st_size


class Server(object):
    def __init__(self, path, port):
        self.path = path
        s = None
        for res in socket.getaddrinfo(None, port, socket.AF_UNSPEC,
                                      socket.SOCK_STREAM, 0,
                                      socket.AI_PASSIVE):
            af, socktype, proto, canonname, sa = res
            try:
                s = socket.socket(af, socktype, proto)
                s.setsockopt(socket.SOL_SOCKET,
                             socket.SO_REUSEADDR, 1)
            except socket.error:
                s = None
                continue
            try:
                s.bind(sa)
                s.listen(1)
            except socket.error:
                s.close()
                s = None
                continue
            break
        if s is None:
            sys.exit(1)
        self.socket = s

    def accept(self):
        conn, addr = self.socket.accept()
        return conn

    def run(self):
        while True:
            conn = self.accept()
            t = threading.Thread(target=self.handleOneConnection, args=(conn,))
            t.daemon = True
            t.start()

    def chunkConsole(self, conn):
        try:
            console = Console(self.path)
        except Exception:
            return
        while True:
            chunk = console.file.read(4096)
            if not chunk:
                break
            conn.send(chunk)
        return console

    def followConsole(self, console, conn):
        while True:
            r = [console.file, conn]
            e = [console.file, conn]
            r, w, e = select.select(r, [], e)

            if console.file in e:
                return True
            if conn in e:
                return False
            if conn in r:
                ret = conn.recv(1024)
                # Discard anything read, if input is eof, it has
                # disconnected.
                if not ret:
                    return False

            if console.file in r:
                line = console.file.readline()
                if line:
                    conn.send(line)
                time.sleep(0.5)
                try:
                    st = os.stat(console.path)
                    if (st.st_ino != console.stat.st_ino or
                        st.st_size < console.size):
                        return True
                except Exception:
                    return True
                console.size = st.st_size

    def handleOneConnection(self, conn):
        # FIXME: this won't notice disconnects until it tries to send
        console = None
        try:
            while True:
                if console is not None:
                    try:
                        console.file.close()
                    except:
                        pass
                while True:
                    console = self.chunkConsole(conn)
                    if console:
                        break
                    time.sleep(0.5)
                while True:
                    if self.followConsole(console, conn):
                        break
                    else:
                        return
        finally:
            try:
                conn.close()
            except Exception:
                pass


def test():
    s = Server('/tmp/console.log', 8088)
    s.run()


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(default='/tmp/console.log'),
            port=dict(default=8088, type='int'),
        )
    )

    p = module.params
    path = p['path']
    port = p['port']

    if daemonize():
        module.exit_json()

    s = Server(path, port)
    s.run()

from ansible.module_utils.basic import *  # noqa

if __name__ == '__main__':
    main()
# test()
