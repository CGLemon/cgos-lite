import traceback
import sys
import select
import time
from master import MasterSocket

def master_loop():
    # Master will initialize all basic status.
    master = MasterSocket()
    commands_queue = list()
    sleeping_time = 0.2

    # The main loop is running.
    try:
        while True:
            # 1st. Check the connecting clients.
            master.handle_clients()

            # 2nd. Try to receive the command.
            master.handle_manager(commands_queue)

            # 3rd. Check the input command.
            read_list, _, _ = select.select([sys.stdin], [], [], 0)
            if read_list:
                cmd = sys.stdin.readline().strip()
                commands_queue.append(cmd)
            master.handle_command(commands_queue)

            # 4th. Check the finished clients.
            master.handle_finished_clients()

            # Sleep some time in order to avoid
            # busy waiting.
            time.sleep(sleeping_time)
    finally:
        master.close()

if __name__ == "__main__":
    try:
        master_loop()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
