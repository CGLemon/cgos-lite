import config

class ClientSocketError(Exception):
    def __init__(self, who, msg):
        self.who = who
        self.msg = msg
        who.crash = True

    def __str__(self):
        return repr(self.msg)

class ClientSocket:
    # It is lazy client. The client can not send any
    # information to server spontaneously. It must
    # wait for commands of server.

    def __init__(self):
        self.name = None
        self.sock = None
        self._sock_file = None
        self.fid = None
        self.support_analysis = False

        # We should remove the client later if crash is true.
        self.crash = False

        # Type is manager or engine.
        self.type = None

    def setup_socket(self, sock):
        if self.sock is not None:
            self.close()
            self.sock = None
        else:
            self.sock = sock
            self.fid = sock.fileno()

        self.create_sockfile()
        msg = self.request_protocol()
        parameters = msg.split()

        if parameters[0] == "e1":
            # The engine client.
            self.support_analysis = "genmove_analyze" in parameters
            self.type = "engine"
        elif parameters[0] == "m1":
            # The manager client.
            self.type = "manager"
        else:
            raise ClientSocketError(self, "Do not soppurt this client version.")

        self.name = self.request_username().strip()
        password = self.request_password()
        if self.type == "manager":
            if password != config.MANAGER_PASSWORD:
                self.crash = True

        # Close the socket file because the we can not push socket file
        # onto process queue. 
        self.close_sockfile()

    def request_poll(self):
        # Not a stand protocal. The effect is to
        # check the socket network connection status.
        try:
            self.request_username()
        except ClientSocketError as e:
            pass

    def request_queries(self):
        # It is for manager client. Try get query from
        # client.
        return self.send_and_receive("queries")

    def request_client_status(self, status):
        # It is for manager client.
        return self.send("status {}".format(status))

    def request_info(self, info):
        # Send the information to client. The client should
        # parse it or store this. There is no return value.
        self.send("info {}".format(info))

    def request_protocol(self):
        # Send the supported protocol type to client. The client
        # should send the version and other information.
        return self.send_and_receive("protocol genmove_analyze")

    def request_username(self):
        # Request the client to send the client's name to server.
        return self.send_and_receive("username")

    def request_password(self):
        # Request the client to send the client's password to server.
        return self.send_and_receive("password")

    def request_setup(self, board_size,
                            komi,
                            main_time_msec,
                            player_a_name,
                            player_b_name):
        # Send the game information to serve, including game id,
        # board size, komi, main think time in milliseconds and 
        # player name. The client should initialize the game.
        # There is no return value.
        game_id = 0
        param = "{} {} {} {} {} {}".format(
                    game_id,
                    board_size,
                    komi,
                    main_time_msec,
                    player_a_name,
                    player_b_name
                )
        return self.send("setup {}".format(param))

    def request_play(self, color, move, time_left_msec):
        # Send the color, coordinate and time left in milliseconds.
        # The client should play this move. Thre is no return value.
        param = "{} {} {}".format(
                    color, move, time_left_msec
                )
        return self.send("play {}".format(param))

    def request_genmove(self, color, time_left_msec):
        # Send the color and time left in milliseconds. The client
        # should send the best move to server.
        param = "{} {}".format(
                    color, time_left_msec
                )
        return self.send_and_receive("genmove {}".format(param))

    def request_gameover(self, date, result, err):
        # Send the game the result to client.
        param = "{} {} {}".format(
                    date, result, err
                )
        return self.send_and_receive("gameover {}".format(param))

    def close(self):
        try:
            self.close_sockfile()
            self.sock.close()
            self.sock = None
            self.fid = None
        except:
            # Invalid the socket if we can not close it.
            self.sock = None
            self.fid = None
            raise ClientSocketError(self, "Can not close the client socket.")

    def create_sockfile(self):
        # We must create socket file before sending the
        # message.
        self.close_sockfile()
        try:
            self._sock_file = self.sock.makefile("rw", encoding="utf-8")
        except:
            raise ClientSocketError(self, "Can not create the socket file.")

    def close_sockfile(self):
        # Close the socket file before pushing onto the
        # process queue because socket file can not be
        # converted to bytes type.
        try:
            if self._sock_file is not None:
                self._sock_file.close()
            self._sock_file = None
        except:
            # Invalid the socket file if we can not close it.
            self._sock_file = None
            raise ClientSocketError(self, "Can not close the socket file.")

    def receive(self):
        msg = None
        try:
            msg = self._sock_file.readline()
        except:
            raise ClientSocketError(self, "Can not read massage from client.")
        if len(msg) == 0:
            # Receive the empty string. It means the
            # client is closed.
            raise ClientSocketError(self, "The client is closed.")
        return msg

    def send(self, msg):
        try:
            self._sock_file.write("{}\n".format(msg))
            self._sock_file.flush()
        except:
            raise ClientSocketError(self, "Can not send massage to client.")

    def send_and_receive(self, msg):
        self.send(msg)
        return self.receive()
