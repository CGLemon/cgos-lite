import socket
import json
import threading
import select
import sys
import queue
import time
import traceback
import tkinter as tk

MANAGER_NAME = "manager"
MANAGER_PASSWORD = "a123456789"
SERVER_PORT = 1919

class ServerSocketError(Exception):
    def __init__(self, who, msg):
        self.who = who
        self.msg = msg
        who.crash = True

    def __str__(self):
        return repr(self.msg)

class ServerSocket:
    def __init__(self, name, password, port):
        self._sock_file = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((socket.gethostname(), port))
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
        try:
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
        except:
            pass


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

    def send_command(self, cmd):
        self.handle_command("command {}".format(cmd))

    def send_match(self,
                   black_fid,
                   white_fid,
                   board_size,
                   komi,
                   main_time,
                   rule,
                   sgf_source,
                   store_path):
        match = "match fid {} {} bsize {} komi {} mtime {} rule {}".format(
            black_fid,
            white_fid,
            board_size,
            komi,
            main_time,
            rule
        )
        if sgf_source is not None:
            match += " sgf {}".format(sgf_source)
        if store_path is not None:
            match += " store {}".format(store_path)
        self.handle_command("command {}".format(match))

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
         port = int(self.port_ety.get())
         password = self.password_ety.get()
         self.server = ServerSocket(
             MANAGER_NAME, self.password_ety.get(), port)
         self.main_layout() 

    def login_layout(self):
        self.clear_frame()
        self.root.geometry("400x150")

        self.label_size = 12
        self.entry_size = 20

        self.port_frame = tk.Frame(self.root)
        self.port_frame.pack(pady=10)
        self.port_lb = tk.Label(
            self.port_frame, text="port",
            width=self.label_size, justify=tk.CENTER)
        self.port_lb.grid(row=0, column=0)
        self.port_ety = tk.Entry(
            self.port_frame, width=self.entry_size, justify=tk.CENTER)
        self.port_ety.insert(0, "{}".format(SERVER_PORT))
        self.port_ety.grid(row=0, column=1)

        self.password_frame = tk.Frame(self.root)
        self.password_frame.pack(pady=10)
        self.password_lb = tk.Label(
            self.password_frame, text="password",
            width=self.label_size, justify=tk.CENTER)
        self.password_lb.grid(row=0, column=0)
        self.password_ety = tk.Entry(
            self.password_frame, width=self.entry_size, justify=tk.CENTER)
        self.password_ety.insert(0, "{}".format(MANAGER_PASSWORD))
        self.password_ety.grid(row=0, column=1)

        self.login_btn = tk.Button(
            self.root, text="Login", command=self.try_login)
        self.login_btn.pack(pady=10)

    def main_layout(self):
        self.clear_frame()
        self.root.geometry("600x450")

        self.clients_lb = tk.Listbox(self.root)
        self.clients_lb.pack(
            side="left", fill='y', padx=10, pady=10)

        self.label_size = 15
        self.entry_size = 20
        self.default_bz = 9
        self.default_komi = 7
        self.default_main_time = 900
 
        self.blk_frame = tk.Frame(self.root)
        self.blk_frame.pack(pady=10)
        self.blk_lb = tk.Label(
            self.blk_frame, text="black fid",
            width=self.label_size, justify=tk.CENTER)
        self.blk_lb.grid(row=0, column=0)
        self.blk_ety = tk.Entry(
            self.blk_frame, width=self.entry_size, justify=tk.CENTER)
        self.blk_ety.grid(row=0, column=1, padx=10)

        self.wht_frame = tk.Frame(self.root)
        self.wht_frame.pack(pady=10)
        self.wht_lb = tk.Label(
            self.wht_frame, text="white fid",
            width=self.label_size, justify=tk.CENTER)
        self.wht_lb.grid(row=0, column=0)
        self.wht_ety = tk.Entry(
            self.wht_frame, justify=tk.CENTER, width=self.entry_size)
        self.wht_ety.grid(row=0, column=1, padx=10)

        self.bz_frame = tk.Frame(self.root)
        self.bz_frame.pack(pady=10)
        self.bz_lb = tk.Label(
            self.bz_frame, text="board size",
            width=self.label_size, justify=tk.CENTER)
        self.bz_lb.grid(row=0, column=0)
        self.bz_ety = tk.Entry(
            self.bz_frame, width=self.entry_size, justify=tk.CENTER)
        self.bz_ety.insert(0, "{}".format(self.default_bz))
        self.bz_ety.grid(row=0, column=1, padx=10)

        self.komi_frame = tk.Frame(self.root)
        self.komi_frame.pack(pady=10)
        self.komi_lb = tk.Label(
            self.komi_frame, text="komi",
            width=self.label_size, justify=tk.CENTER)
        self.komi_lb.grid(row=0, column=0)
        self.komi_ety = tk.Entry(
            self.komi_frame, width=self.entry_size, justify=tk.CENTER)
        self.komi_ety.insert(0, "{}".format(self.default_komi))
        self.komi_ety.grid(row=0, column=1, padx=10)

        self.mt_frame = tk.Frame(self.root)
        self.mt_frame.pack(pady=10)
        self.mt_lb = tk.Label(
            self.mt_frame, text="main time",
            width=self.label_size, justify=tk.CENTER)
        self.mt_lb.grid(row=0, column=0)
        self.mt_ety = tk.Entry(
            self.mt_frame, width=self.entry_size, justify=tk.CENTER)
        self.mt_ety.insert(0, "{}".format(self.default_main_time))
        self.mt_ety.grid(row=0, column=1, padx=10)

        self.store_frame = tk.Frame(self.root)
        self.store_frame.pack(pady=10)
        self.store_lb = tk.Label(
            self.store_frame, text="store path",
            width=self.label_size, justify=tk.CENTER)
        self.store_lb.grid(row=0, column=0)
        self.store_ety = tk.Entry(
            self.store_frame, width=self.entry_size, justify=tk.CENTER)
        self.store_ety.grid(row=0, column=1, padx=10)


        self.rule_frame = tk.Frame(self.root)
        self.rule_frame.pack(pady=10)
        self.rule_lb = tk.Label(
            self.rule_frame, text="rule",
            width=self.label_size, justify=tk.CENTER)
        self.rule_lb.grid(row=0, column=0)
        self.rule_lb = tk.Listbox(
            self.rule_frame, height=1,
            width=self.entry_size, justify=tk.CENTER)
        self.rule_lb.grid(row=0, column=1, padx=10)
        for r in ["chinese-like", "null"]:
            self.rule_lb.insert(tk.END, r)

        self.match_btn = tk.Button(
            self.root,
            text="Match",
            width=20,
            command=self.do_match)
        self.match_btn.pack(pady=10)

        # self.refresh_btn = tk.Button(
        #     self.root,
        #     text="Refresh",
        #     width=20,
        #     command=self.update_clients)
        # self.refresh_btn.pack(pady=10)

        self.cmd_ety = tk.Entry(
            self.root, width=2*self.entry_size, justify=tk.CENTER)
        self.cmd_ety.pack(pady=10)

        self.cmd_btn = tk.Button(
            self.root,
            text="Send",
            width=20,
            command=self.send_command)
        self.cmd_btn.pack(pady=10)

        self.update_clients()

    def do_match(self):
        def is_int(v):
            try:
                int(v)
            except:
                return False
            return True
        def is_float(v):
            try:
                float(v)
            except:
                return False
            return True

        def check_player_valid(client_status, fid):
            if client_status.get(str(fid), None) is None:
                return False
            if client_status[str(fid)] == "playing":
                return False
            return True

        b = self.blk_ety.get()
        w = self.wht_ety.get()
        bz = self.bz_ety.get()
        k = self.komi_ety.get()
        mt = self.mt_ety.get()
        st = self.store_ety.get()

        if is_int(b):
            black_fid = int(b)
        else:
            print("The black fid is not integer.")
            return

        if is_int(w):
           white_fid = int(w)
        else:
            print("The white fid is not integer.")
            return

        if is_int(bz):
            board_size = int(bz)
        else:
            print("The board size is not integer.")
            return

        if is_float(k):
            komi = float(k)
        else:
            print("The komi is not float.")
            return

        if is_int(mt):
            main_time = int(mt)
        else:
            print("The main time is not integer.")
            return

        # if not check_player_valid(self.client_status, black_fid):
        #     print("It is invalid black player.")
        #     return

        # if not check_player_valid(self.client_status, white_fid):
        #     print("It is invalid white player.")
        #     return

        if len(st) == 0:
            store_path = None
        else:
            store_path = st

        rule = self.rule_lb.get(self.rule_lb.nearest(0))

        self.blk_ety.delete(0, tk.END)
        self.wht_ety.delete(0, tk.END)
        self.server.send_match(
            black_fid,
            white_fid,
            board_size,
            komi,
            main_time,
            rule,
            None,
            store_path)

    def send_command(self):
        c = self.cmd_ety.get()
        self.cmd_ety.delete(0, tk.END)
        self.server.send_command(c)

    def update_clients(self):
        self.client_status = self.server.get_client_status()
        self.clients_lb.delete(0, tk.END)

        for v, k in self.client_status.items():
            where = 0 if k["type"] == "manager" else tk.END
            prefix = " * " if k["type"] == "manager" else \
                         "({}) ".format(k["gid"]) \
                             if k["status"] == "playing" else "   "
            self.clients_lb.insert(
                where,
                "{}{} ({})".format(
                    prefix,
                    k["name"], # name
                    v          # fid
                )
            )
        self.root.after(1000, self.update_clients)

    def clear_frame(self):
        for widgets in self.root.winfo_children():
            widgets.destroy()

    def __del__(self):
        if self.server is not None:
            self.server.abort()

if __name__ == "__main__":
    try:
        m = ManagerGUI()
    except:
        traceback.print_exc()
        sys.exit(1)
