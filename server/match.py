import time

class ClientStatus:
    def __init__(self, sock):
        self.name = None
        self.sock = sock
        self.fid = sock.fileno()
        self.support_analysis = False

    def fetch_status(self):
        msg = self.send_and_receive("protocol genmove_analyze")

        if msg[0:2] == "e1":
            parameters = msg.split()
            self.support_analysis = "genmove_analyze" in parameters
        else:
            raise Exception("do not soppurt this version")

        self.name = self.send_and_receive("username")
        self.send_and_receive("password") # not used...

    def close(self):
        self.sock.close()
            
    def receive(self):
        msg = None
        try:
            msg = self.sock.read()
        except:
            raise Exception("can not read massage from client")
        return msg

    def send(self, msg):
        try:
            self.sock.write(msg)
        except:
            raise Exception("can not send massage to client")

    def send_and_receive(self, msg):
        self.send(msg)
        return self.receive()


def match_loop(ready_queue, finished_queue):
    while True:
        try:
            black, white = ready_queue.get()
        except queue.Empty:
            time.sleep(1)
            continue


        # do the match game ....

        finished_queue.put((black, white))

