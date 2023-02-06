import socket
import traceback
import sys
import select
import random
import queue
import os
import multiprocessing as mp

import config
from match import ClientSocket, match_loop

def master_loop():
    # Make the SGF files directory.
    sgf_path = os.path.join(*config.SGF_DIR_PATH)
    if not os.path.isdir(sgf_path):
        os.mkdir(sgf_path)

    # Allocate all data structure.
    client_pool = dict()
    process_pool = list() 
    commands_queue = list()
    ready_queue = mp.Queue()
    finished_queue = mp.Queue()
    last_game_id = 0

    # Allocate the process(s).
    num_workers = config.NUM_WORKERS
    if num_workers is None:
        num_workers = os.cpu_count()
    num_workers = max(num_workers, 1)
    for i in range(num_workers):
        p = mp.Process(
                target=match_loop,
                args=(ready_queue, finished_queue, ),
                daemon=True
            )
        p.start()
        process_pool.append(p)

    # Start the main server socket.
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("", config.SERVER_PORT))
    server_sock.listen(10)

    print("The client is ready.")

    # Start the master loop. There are 3 stages.
    # 1st. Check the connecting clients.
    # 2nd. Check the user command.
    # 3rd. Check the finished queue.
    try:
        while True:
            # 1st. Check the connecting clients.
            read_list = [server_sock]
            readable, _, err = select.select(read_list, [], read_list, 0.1)

            for s in err:
                # Some mistake in the client. Close it. 
                fid = s.fileno()
                c = client_pool.pop(fid, None)
                if c is not None:
                    c.close()

            for s in readable:
                if s is server_sock:
                    # New client connects to the server.
                    client_sock, _ = server_sock.accept()
                    fid = client_sock.fileno()
                    c = ClientSocket()
                    c.setup_socket(client_sock)
                    client_pool[fid] = c
                    outs_info = "The socket {} [{}] connects to the server".format(
                                    fid, c.name
                                )
                    print(outs_info)

            # 2nd. Check the user command.
            read_list, _, _ = select.select([sys.stdin], [], [], 0)
            if read_list:
                cmd = sys.stdin.readline().strip()
                commands_queue.append(cmd)

            if len(commands_queue) != 0:
                commands_queue.pop(0)
                cmd_list = cmd.split()
                print("Get command [{}]...".format(cmd))

                if cmd_list[0] == "quit":
                    # Should close all client sockets and release
                    # all process in the pool.
                    for k, v in client_pool.items():
                        print("Close the socket {}.".format(k))
                        v.close()
                    print("Release the process pool.")
                    for p in process_pool:
                        p.terminate()
                    sys.exit(1)
                elif cmd_list[0] == "show" and len(cmd_list) == 2:
                    # Show some server status.
                    if cmd_list[1] == "clients":
                        for k, v in client_pool.items():
                            print("fid: {} -> {}".format(k, v.name))

                elif cmd_list[0] == "match":
                    # The "match" command will select two waiting clients
                    # for match game. Here are the valid commands
                    #     "random" : randomly select two clients
                    #     "fid"    : select two clients with socket id
                    #     "file"   : not yet
                    keys = list(client_pool.keys())
                    task = { "id" : last_game_id }

                    if len(keys) <= 1:
                        print("There are not enough ready clients.")
                    elif len(cmd_list) <= 1:
                        print("Miss some paramters.")
                    elif cmd_list[1] == "random":
                        random.shuffle(keys)
                        task["black"] = client_pool.pop(keys.pop(0)) # black player
                        task["white"] = client_pool.pop(keys.pop(0)) # white player
                    elif cmd_list[1] == "fid":
                        # Keep to get the setting paramter. Must provide black
                        # fid and white fid. Two fids must be different. Others
                        # are optional. The format is
                        # format is
                        #
                        # match fid 100 200
                        # match fid 100 200 bsize 17
                        # match fid 100 200 mtime 900 bsize 19 komi 7.5

                        i = 0
                        for c in cmd_list:
                            field = None
                            if i == 2:
                                black_fid = int(c) # black player
                                task["black"] = client_pool.pop(black_fid, None)
                            elif i == 3:
                                white_fid = int(c) # black player
                                task["white"] = client_pool.pop(white_fid, None)
                            elif i >= 4:
                                # Optional fields, it is not necessary. Use the
                                # default value if we do not give key-value pair. 
                                if field is None:
                                    field = c
                                elif field == "mtime":
                                    task["main_time"] = int(c) # get main time
                                    field = None
                                elif field == "bsize":
                                    task["board_size"] = int(c) # get board size
                                    field = None
                                elif field == "komi":
                                    task["komi"] = float(c) # get komi
                                    field = None
                                else:
                                    field = None
                            i += 1

                    if task.get("black", None) is not None and \
                           task.get("white", None) is not None:
                        # The current setting is valid. Push the task
                        # to ready queue.
                        ready_queue.put(task)
                        outs_info = "New match game {}, black is {} and white is {}.".format(
                                        last_game_id,
                                        task["black"].name,
                                        task["white"].name
                                    )
                        print(outs_info)
                        last_game_id += 1
                else:
                    print("Invalid command [{}]...".format(cmd))

            # 3rd. Check the finished queue.
            try:
                # Collect the finished clients from queue. Reset the
                # clients status to waiting.
                task = finished_queue.get(block=True, timeout=0.1)
                black, white = task["black"], task["white"]
                client_pool[black.fid] = black
                client_pool[white.fid] = white
                print("The match game {} is over.".format(task["id"]))
            except queue.Empty:
                pass
    finally:
        server_sock.close()

if __name__ == "__main__":
    try:
        master_loop()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
