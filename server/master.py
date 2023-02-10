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
        # The processes run the match games.
        self.process_pool = list() 

        # Record current the match game and clients status.
        self.game_tasks = dict()
        self.client_pool = dict()

        # There are tree pipe to control the match games
        # schedule. Their relation are here.
        #
        # Add new clients: (get the socket) => waiting_clients
        # schedule game:    waiting_clients => ready_queue_pool
        # playing game:    ready_queue_pool => (thread running...) => finished_queue
        # finshed game:      finished_queue => waiting_clients
        # terninate:        waiting_clients => (close the socket)
        self.waiting_clients = set()
        self.ready_queue_pool = list() # One process uses one independent ready queue.
        self.finished_queue = mp.Queue() # All processes share one finished queue.
        self.last_game_id = 0
        self.should_remove_fids = set()

        # Set the logging file.
        self.logger = self.get_and_setup_logging(
                          "master.MasterSocket",
                          "log.txt",
                          sys.stdout
                      )

        # Make the SGF files directory. We will save
        # the match games here.
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

    def get_and_setup_logging(self, name, out_file, out_io):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # Log debug output to file
        handler = logging.FileHandler(out_file)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Log info output to console
        handler = logging.StreamHandler(out_io)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def handle_clients(self):
        read_list = [self.server_sock]
        readable, _, err = select.select(read_list, [], read_list, 0.1)

        for s in err:
            # Some mistake in the client. Close it. 
            fid = s.fileno()
            c = self.client_pool.get(fid, None)
            if c is not None:
                self.should_remove_fids.add(fid)
                outs_info = "The socket {} (\"{}\") is closed.".format(
                                fid, c["socket"].name
                            )
                self.logger.info(outs_info)

        for s in readable:
            if s is self.server_sock:
                # New client connects to the server.
                client_sock, _ = self.server_sock.accept()
                fid = client_sock.fileno()
                c = ClientSocket()
                c.setup_socket(client_sock)
                self.waiting_clients.add(fid)
                self.client_pool[fid] = {
                    "socket" : c,
                    "status" : "waiting",
                    "pid"    : None,
                    "gid"    : None
                }
                outs_info = "The socket {} (\"{}\") connects to the server.".format(
                                fid, c.name
                            )
                self.logger.info(outs_info)

        for fid, v in self.client_pool.items():
            # Check the crash socket.
            if v["socket"].crash:
                self.should_remove_fids.add(fid)

        for fid in self.should_remove_fids:
            # Don't remove the waiting_clients here because
            # It may be in the match game. We will synchronize
            # it later.
            c = self.client_pool.pop(fid, None)
            try:
                # Maybe the socket be closed.
                c["socket"].close()
            except:
                pass
        self.should_remove_fids.clear()

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

        # Synchronize the waiting_clients here. Remove
        # the closed socket fids.
        wc_list = list(self.waiting_clients)
        for fid in wc_list:
            c = self.client_pool.get(fid, None)
            if c is None:
                self.waiting_clients.remove(fid)

        self.logger.info("Get command [\"{}\"]...".format(cmd))

        if cmd_list["main"] == "quit":
            # End the program.
            for k, v in self.client_pool.items():
                self.logger.info("Close the socket {}.".format(k))
                v["socket"].close()
            self.logger.info("Terminate the process pool.")

            for p in self.process_pool:
                p["proc"].terminate()
            # Be careful that the "quit" will finish the
            # program. We should close all sockets, terminate
            # all processes and do other important things
            # before it.
            sys.exit(1)
        elif cmd_list["main"] == "close":
            # Close a socket via fids.
            i = 0
            for c in cmd_list_raw:
                if i >= 1:
                    try:
                        fid = int(cmd_list.get(i, None))
                        self.should_remove_fids.add(fid)
                    except:
                        continue
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
                for k, v in self.client_pool.items():
                    #TODO: better information format
                    out_info = "    fid: {} -> {}, {}, {}, {}".format(
                                   k, v["socket"].name, v["status"], v["gid"], v["pid"])
                    self.logger.info(out_info)
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
            keys = list(self.waiting_clients)
            task = {
                "black" : None,
                "white" : None,
                "gid" : self.last_game_id
            }

            if len(keys) <= 1:
                self.logger.info("There are not enough ready clients.")
            elif cmd_list.get(1, None) == "random":
                random.shuffle(keys)
                black_fid = keys.pop(0)
                white_fid = keys.pop(0)

                for name, fid in zip(["black", "white"], [black_fid, white_fid]):
                    self.waiting_clients.remove(fid)
                    task[name] = self.client_pool[fid]["socket"]
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
                    if i == 2 or i == 3:
                        names = ["black", "white"]
                        try:
                            fid = int(c) # may fail here
                            if fid in self.waiting_clients:
                                self.waiting_clients.remove(fid)
                                task[names[i-2]] = self.client_pool[fid]["socket"]
                        except:
                            pass
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

                for name in ["black", "white"]:
                    fid = task[name].fid
                    self.client_pool[fid]["status"] = "playing"
                    self.client_pool[fid]["gid"] = task["gid"]
                    self.client_pool[fid]["pid"] = task["pid"]

                self.game_tasks[task["gid"]] = task

                outs_info = "The new match game {} in the process {}, {}(B) vs {}(W).".format(
                                task["gid"],
                                task["pid"],
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
                    self.waiting_clients.add(black.fid)
                if white is not None:
                    self.waiting_clients.add(white.fid)
        else:
            self.logger.info("Invalid command [{}]...".format(cmd))

    def handle_finished_clients(self):
        try:
            # Collect the finished clients from queue. Reset the
            # clients status to waiting.
            task = self.finished_queue.get(block=True, timeout=0.1)
            black, white, pid = task["black"], task["white"], task["pid"]
            self.process_pool[pid]["load"] -= 1
            self.waiting_clients.update({black.fid, white.fid})
            for fid in [black.fid, white.fid]:
                self.client_pool[fid]["status"] = "waiting"
                self.client_pool[fid]["pid"] = None
                self.client_pool[fid]["gid"] = None
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
