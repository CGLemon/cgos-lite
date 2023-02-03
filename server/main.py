import socket
import traceback
import sys
import select
import random
import queue
import os
import multiprocessing as mp

import config
from match import ClientStatus, match_loop

def master_loop():
    # Allocate all data structure.
    client_pool = dict()
    process_pool = list() 
    ready_queue = mp.Queue()
    finished_queue = mp.Queue()

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

    # Start the master loop. There are 3 stages.
    # 1. Check the connecting clients.
    # 2. Check the user command.
    # 3. Check the finished queue.
    try:
        while True:
            # 1. Check the connecting clients.
            read_list = [server_sock]
            readable, _, err = select.select(read_list, [], read_list, 0.1)

            for s in err:
                fid = s.fileno()
                c = client_pool.pop(fid, None)
                if c is not None:
                    c.close()

            for s in readable:
                if s is server_sock:
                    client_sock, _ = server_sock.accept()
                    fid = client_sock.fileno()
                    c = ClientStatus()
                    c.setup_socket(client_sock)
                    client_pool[fid] = c
                    print("The socket {} connects to the server".format(fid))

            # 2. Check the user command.
            read_list, _, _ = select.select([sys.stdin], [], [], 0)
            if read_list:
                cmd = sys.stdin.readline().strip()
                print("Get command [{}]...".format(cmd))

                if cmd == "quit":
                    # Should close all client sockets and release
                    # all process in the pool.
                    for k, v in client_pool.items():
                        print("Close the socket {}.\n".format(k))
                        v.close()
                    print("Release the process pool.")
                    for p in process_pool:
                        p.terminate()
                    sys.exit(1)
                elif cmd == "match random":
                    # Random select two clients for the new match
                    # game.
                    keys = list(client_pool.keys())
                    if len(keys) >= 2:
                        random.shuffle(keys)
                        black_fid = keys.pop(0)
                        white_fid = keys.pop(0)

                        black = client_pool.pop(black_fid)
                        white = client_pool.pop(white_fid)

                        outs_info = "New match game, black is {} and white is {}".format(
                                        black.name, white.name
                                    )
                        print(outs_info)
                        ready_queue.put((black, white))
                    else:
                        print("There are not enough ready clients.")
                else:
                    print("Invalid command [{}]...".format(cmd))

            # 3. Check the finished queue.
            try:
                black, white = finished_queue.get(block=True, timeout=0.1)
                client_pool[black.fid] = black
                client_pool[white.fid] = white
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
