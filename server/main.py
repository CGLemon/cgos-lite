import socket
import traceback
import sys
import select
import random
import multiprocessing as mp

import config
from match import ClientStatus



def master_loop():
    clients_pool = dict()
    ready_queue = mp.Queue()
    finished_queue = mp.Queue()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((socket.gethostname(), config.SERVER_PORT))
    server_sock.listen(config.MAX_SOCKETS)

    try:
        while True:
            read_list = [server_sock]
            readable, _, err = select.select(read_list, [], read_list, 1)

            for s in err:
                fid = s.fileno()
                c = clients_pool.pop(fid, None)
                if c is not None:
                    c.close()

            for s in readable:
                if s is server_sock:
                    client_sock, _ = server_sock.accept()
                    fid = client_sock.fileno()
                    c = ClientStatus(client_sock)
                    c.fetch_status()
                    clients_pool[fid] = c
                    print("Conect the socket {}".format(fid))

            read_list, _, _ = select.select([sys.stdin], [], [], 0)
            if read_list:
                cmd = sys.stdin.readline().strip()

                if cmd == "quit":
                    for k, v in clients_pool.items():
                        print("Close the socket {}.\n".format(k))
                        v.close()
                    sys.exit(1)
                else if cmd == "match random":
                    keys = list(dishes.keys())
                    if len(keys) >= 2:
                        random.shuffle(keys)
                        black_fid = keys.pop(0)
                        white_fid = keys.pop(0)

                        black = clients_pool.pop(black_fid)
                        white = clients_pool.pop(white_fid)
                        ready_queue.put((black, white))

            try:
                black, white = finished_queue.get()
                clients_pool[black.fid] = black
                clients_pool[white.fid] = white
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

