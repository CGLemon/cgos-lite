import socket
import select
import queue
import random
import os
import sys
import logging
import multiprocessing as mp

import config
from match import ClientSocket, match_loop

class MasterSocket:
    def __init__(self):
        # TODO: We should record each games and clients status in
        #       order to control the games.
        self.process_pool = list() 
        self.waiting_clients = dict()
        self.ready_queue_pool = list()
        self.finished_queue = mp.Queue()
        self.last_game_id = 0

        # Set the logging file.
        self.logger = logging.getLogger("master.MasterSocket")
        self.logger.setLevel(logging.DEBUG)

        # Log debug output to file
        handler = logging.FileHandler("log.txt")
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Log info output to console
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s: %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Make the SGF files directory. We will
        # save the match games here.
        sgf_path = os.path.join(*config.SGF_DIR_PATH)
        if not os.path.isdir(sgf_path):
            os.mkdir(sgf_path)

        # Allocate the process(s).
        num_workers = config.NUM_WORKERS
        if num_workers is None:
            # TODO: Should I leave one core for master?
            num_workers = os.cpu_count()
        for i in range(max(num_workers, 1)):
            pid = i
            self.ready_queue_pool.append(mp.Queue())
            p = mp.Process(
                    target=match_loop,
                    args=(pid, self.ready_queue_pool[pid], self.finished_queue, ),
                    daemon=True
                )
            p.start()
            self.process_pool.append(
                { 
                    "proc" : p,  # The process.
                    "load" : 0,  # The number of running games.
                    "pid"  : pid # The process id.
                }
            )

        # Build the master socket.
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.bind(("", config.SERVER_PORT))
        self.server_sock.listen(10)
        self.logger.info("The client is ready.")

    def handle_clients(self):
        read_list = [self.server_sock]
        readable, _, err = select.select(read_list, [], read_list, 0.1)

        for s in err:
            # Some mistake in the client. Close it. 
            fid = s.fileno()
            c = self.waiting_clients.pop(fid, None)
            if c is not None:
                c.close()

        for s in readable:
            if s is self.server_sock:
                # New client connects to the server.
                client_sock, _ = self.server_sock.accept()
                fid = client_sock.fileno()
                c = ClientSocket()
                c.setup_socket(client_sock)
                self.waiting_clients[fid] = c
                outs_info = "The socket {} (\"{}\") connects to the server.".format(
                                fid, c.name
                            )
                self.logger.info(outs_info)

    def handle_command(self, commands_queue):
        if len(commands_queue) == 0:
            return

        cmd = commands_queue.pop(0)
        cmd_list_raw = cmd.split()
        cmd_list = dict()

        if len(cmd_list_raw) == 0:
            return

        for i in range(len(cmd_list_raw)):
            cmd_list[i] = cmd_list_raw[i]
        cmd_list["main"] = cmd_list_raw[0]

        self.logger.info("Get command [\"{}\"]...".format(cmd))

        if cmd_list["main"] == "quit":
            # End the program.
            for k, v in self.waiting_clients.items():
                self.logger.info("Close the socket {}.".format(k))
                v.close()
            self.logger.info("Terminate the process pool.")

            for p in self.process_pool:
                p["proc"].terminate()
            # Be careful that the "quit" will finish the
            # program. We should close all sockets, terminate
            # all processes and do other important things
            # before it.
            sys.exit(1)
        elif cmd_list["main"] == "file":
            # Read the batched commands from file. one line
            # should be one command. For example,
            #
            # ==== batched.txt ====
            # show client
            # show process
            # match random
            filenames = list()
            i = 0
            for c in cmd_list_raw:
                if i >= 1:
                    filenames.append(c)
                i += 1

            for n in filenames:
                with open(n, 'r') as f:
                    line = f.readline()
                    while len(line) != 0:
                        commands_queue.append(line.strip())
                        line = f.readline()

        elif cmd_list["main"] == "show":
            # Show some server status.
            if cmd_list.get(1, None) == "client":
                for k, v in self.waiting_clients.items():
                    self.logger.info("    fid: {} -> {}".format(k, v.name))
            elif cmd_list.get(1, None) == "process":
                for p in self.process_pool:
                    self.logger.info("    pid: {} -> {}".format(p["pid"], p["load"]))
            else:
                self.logger.info("Unknown parameter.")

        elif cmd_list["main"] == "match":
            # The "match" command will select two waiting clients
            # for match game. Here are the valid commands
            #     "random" : randomly select two clients
            #     "fid"    : select two clients with socket id
            keys = list(self.waiting_clients.keys())
            task = { "gid" : self.last_game_id }

            if len(keys) <= 1:
                self.logger.info("There are not enough ready clients.")
            elif cmd_list.get(1, None) == "random":
                random.shuffle(keys)
                task["black"] = self.waiting_clients.pop(keys.pop(0)) # black player
                task["white"] = self.waiting_clients.pop(keys.pop(0)) # white player
            elif cmd_list.get(1, None) == "fid":
                # Keep to get the setting paramter. Must provide black
                # fid and white fid. Two fids must be different. Others
                # are optional. The format is
                #
                # match fid 100 200
                # match fid 100 200 bsize 17
                # match fid 100 200 mtime 900 bsize 19 komi 7.5

                i = 0
                for c in cmd_list_raw:
                    field = None
                    if i == 2:
                        task["black"] = self.waiting_clients.pop(int(c), None) # black player
                    elif i == 3:
                        task["white"] = self.waiting_clients.pop(int(c), None) # white player
                    elif i >= 4:
                        # Optional fields, it is not necessary. Use the
                        # default value if we do not give key-value pair. 
                        if field is None:
                            field = c
                        else:
                            if field == "mtime":
                                task["main_time"] = int(c) # get main time
                            elif field == "bsize":
                                task["board_size"] = int(c) # get board size
                            elif field == "komi":
                                task["komi"] = float(c) # get komi
                            field = None # clean the field
                    i += 1
            else:
                self.logger.info("Unknown parameter.")

            if task.get("black", None) is not None and \
                   task.get("white", None) is not None:
                # Select the lowest load process in order to
                # load balancing.
                min_load = self.process_pool[0]["load"]
                select_pid = self.process_pool[0]["pid"]
                for p in self.process_pool:
                    if min_load < p["load"]:
                        min_load = p["load"]
                        select_pid = p["pid"]
                task["pid"] = select_pid
                self.process_pool[select_pid]["load"] += 1

                # The current setting is valid. Push the task
                # to ready queue.
                self.ready_queue_pool[select_pid].put(task)

                outs_info = "The new match game {} in the process {}, {}(B) vs {}(W).".format(
                                self.last_game_id,
                                select_pid,
                                task["black"].name,
                                task["white"].name
                            )
                self.logger.info(outs_info)
                self.last_game_id += 1
            else:
                # If the task is invalid, return the clients to
                # waiting list.
                black, white = task.get("black", None), task.get("white", None)
                if black is not None:
                    self.waiting_clients[black.fid] = black
                if white is not None:
                    self.waiting_clients[white.fid] = white
        else:
            self.logger.info("Invalid command [{}]...".format(cmd))

    def handle_finished_clients(self):
        try:
            # Collect the finished clients from queue. Reset the
            # clients status to waiting.
            task = self.finished_queue.get(block=True, timeout=0.1)
            black, white, pid = task["black"], task["white"], task["pid"]
            self.process_pool[pid]["load"] -= 1
            self.waiting_clients[black.fid] = black
            self.waiting_clients[white.fid] = white
            self.logger.info("The match game {} is over.".format(task["gid"]))
        except queue.Empty:
            pass

    def close(self):
        try:
            if self.server_sock is not None:
                self.server_sock.close()
                self.server_sock = None
        except:
            raise Exception("Can not close the master socket.")

    def __del__(self):
        self.close();
