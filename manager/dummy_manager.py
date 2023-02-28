import socket
import json
import threading
import select
import sys
import queue
import time

PORT_VAL = 1919

class ClientSocketError(Exception):
    def __init__(self, who, msg):
        self.who = who
        self.msg = msg
        who.crash = True

    def __str__(self):
        return repr(self.msg)

class ClientSocket:
    def __init__(self, name, password):
        self._sock_file = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((socket.gethostname(), PORT_VAL))
        self.name = name
        self.password = password
        self.running = True
        self.loop = threading.Thread(
                        target=self.receive_loop,
                        args=(),
                        daemon=True
                    )
        self.loop.start()
        self.query_queue = queue.Queue()

    def handle_command(self, cmd):
        cmd_list = cmd.split()
        query = dict()
        if len(cmd_list) == 0:
            print("There is no inputs.")
            return
        if cmd_list[0] == "client_status":
            self.query_queue.put(("client_status", query))
        elif cmd_list[0] == "command":
            val = str()
            cmd_list.pop(0)
            for v in cmd_list:
                val += "{} ".format(v)
            self.query_queue.put(("command", val.strip()))

    def abort(self):
        self.running = False
        self.loop.join()

    def receive_loop(self):
        self.create_sockfile()
        while self.running:
            msg = self.receive()
            if len(msg) == 0:
                time.sleep(1)
                continue
            msg_list = msg.split()
            if msg_list[0] == "protocol":
                self.handle_protocol()
            elif msg_list[0] == "username":
                self.handle_username()
            elif msg_list[0] == "password":
                self.handle_password()
            elif msg_list[0] == "client_status":
                self.handle_client_status(msg)
            elif msg_list[0] == "queries":
                self.handle_queries()
        self.close()

    def handle_protocol(self):
        self.send("m1")

    def handle_username(self):
        self.send(self.name)

    def handle_password(self):
        self.send(self.password)

    def handle_client_status(self, msg):
        print(msg)

    def handle_queries(self):
        queries = dict()

        while not self.query_queue.empty():
            key, query = self.query_queue.get(block=True, timeout=0)
            queries[key] = query

        if len(queries) == 0:
            self.send("")
        else:
            self.send("{}".format(json.dumps(queries, indent=None, separators=(',', ':'))))


    def close(self):
        try:
            self.close_sockfile()
            self.sock.close()
            self.sock = None
        except:
            # Invalid the socket if we can not close it.
            self.sock = None
            raise ClientSocketError(self, "Can not close the client socket.")


    def create_sockfile(self):
        self.close_sockfile()
        try:
            self._sock_file = self.sock.makefile("rw", encoding="utf-8")
        except:
            raise ClientSocketError(self, "Can not create the socket file.")

    def close_sockfile(self):
        try:
            if self._sock_file is not None:
                self._sock_file.close()
            self._sock_file = None
        except:
            # Invalid the socket file if we can not close it.
            self._sock_file = None
            raise ClientSocketError(self, "Can not close the socket file.")

    def receive(self):
        msg = None
        try:
            msg = self._sock_file.readline()
        except:
            raise ClientSocketError(self, "Can not read massage from client.")
        if len(msg) == 0:
            raise ClientSocketError(self, "The client is closed.")
        return msg.strip()


    def send(self, msg):
        try:
            self._sock_file.write("{}\n".format(msg))
            self._sock_file.flush()
        except:
            raise ClientSocketError(self, "Can not send massage to server.")

if __name__ == "__main__":
    c = ClientSocket("manager", "a123456789")
    while True:
        read_list, _, _ = select.select([sys.stdin], [], [], 0)
        if read_list:
            cmd = sys.stdin.readline().strip()
            if cmd == "quit":
                c.abort()
                sys.exit(1)
            else:
                c.handle_command(cmd)

# command show client
# command match random
