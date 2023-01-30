import socket
import traceback
import sys
import select

import config
from match import ClientStatus

def remove_clients(c_dict, fid):
    c = c_dict.pop(fid, None)
    if c is not None:
        c.close()

def master_loop():
    clients_pool = dict()

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
    finally:
        server_sock.close()


if __name__ == "__main__":
    try:
        master_loop()
    except Exception:
        traceback.print_exc()
        sys.exit(1)

