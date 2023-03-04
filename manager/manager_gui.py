import socket
import json
import threading
import select
import sys
import queue
import time
import tkinter as tk

SERVER_PORT = 1919
MANAGER_NAME = "manager"
MANAGER_PASSWORD = "a123456789"

class ServerSocketError(Exception):
    def __init__(self, who, msg):
        self.who = who
        self.msg = msg
        who.crash = True

    def __str__(self):
        return repr(self.msg)

class ServerSocket:
    def __init__(self, name, password):
        self._sock_file = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((socket.gethostname(), SERVER_PORT))
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
        self.client_status_queue = queue.Queue()

    def handle_command(self, cmd, block=False):
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
        msg = msg[len("client_status"):]
        self.client_status_queue.put(json.loads(msg))

    def handle_queries(self):
        queries = dict()

        while not self.query_queue.empty():
            key, query = self.query_queue.get(block=True, timeout=0)
            queries[key] = query

        if len(queries) == 0:
            self.send("")
        else:
            self.send("{}".format(json.dumps(queries, indent=None, separators=(',', ':'))))

    def get_client_status(self):
        self.handle_command("client_status")
        out = self.client_status_queue.get(block=True, timeout=9999)
        return out

    def close(self):
        try:
            self.close_sockfile()
            self.sock.close()
            self.sock = None
        except:
            # Invalid the socket if we can not close it.
            self.sock = None
            raise ServerSocketError(self, "Can not close the server socket.")


    def create_sockfile(self):
        self.close_sockfile()
        try:
            self._sock_file = self.sock.makefile("rw", encoding="utf-8")
        except:
            raise ServerSocketError(self, "Can not create the socket file.")

    def close_sockfile(self):
        try:
            if self._sock_file is not None:
                self._sock_file.close()
            self._sock_file = None
        except:
            # Invalid the socket file if we can not close it.
            self._sock_file = None
            raise ServerSocketError(self, "Can not close the socket file.")

    def receive(self):
        msg = None
        try:
            msg = self._sock_file.readline()
        except:
            raise ServerSocketError(self, "Can not read massage from server.")
        if len(msg) == 0:
            raise ServerSocketError(self, "The server is closed.")
        return msg.strip()


    def send(self, msg):
        try:
            self._sock_file.write("{}\n".format(msg))
            self._sock_file.flush()
        except:
            raise ServerSocketError(self, "Can not send massage to server.")

class ManagerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.client_status = dict()

        self.root.title("CGOS-Lite Manager")
        self.root.resizable(True, True)
        self.server = None

        self.login_layout()
        self.root.mainloop()

    def try_login(self):
         p = self.password_entry.get()
         print(p)

         self.server = ServerSocket(MANAGER_NAME, MANAGER_PASSWORD)
         self.main_layout() 

    def login_layout(self):
        self.clear_frame()
        self.password_lable = tk.Label(self.root, text="Password:")
        self.password_entry = tk.Entry(self.root)
        self.password_lable.grid(row=0, column=0, padx=10, pady=10)
        self.password_entry.grid(row=0, column=1, padx=10, pady=10)

        self.login_button = tk.Button(
            self.root, text="Login", command=self.try_login)
        self.login_button.grid(row=1, column=0, padx=10, pady=10)

    def main_layout(self):
        self.clear_frame()
        self.root.geometry("800x600")

        self.clients_listbox = tk.Listbox(self.root)
        self.clients_listbox.pack(
            side="left", fill='y', padx=10, pady=10)

        self.update_baisc()

    def update_baisc(self):
        client_status = self.server.get_client_status()

        self.clients_listbox.delete(0, tk.END)
        for v, k in client_status.items():
            where = "0" if k[1] == "manager" else tk.END
            prefix = " * " if k[1] == "manager" else "   "

            self.clients_listbox.insert(
                where,
                "{}{} ({})".format(
                    prefix,
                    k[0], # name
                    v     # fid
                )
            )
        self.root.after(2000, self.update_baisc)

    def clear_frame(self):
        for widgets in self.root.winfo_children():
            widgets.destroy()

    def __del__(self):
        if self.server is not None:
            self.server.abort()

if __name__ == "__main__":
    m = ManagerGUI()

# command show client
# command match random
