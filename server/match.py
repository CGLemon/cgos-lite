import time
import board
import config

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

def play_match_game(black, white, setting):
    def color_to_char(c):
        if c == board.BLACK:
            return 'b'
        return 'w'

    def get_opp_color(c):
        if c == board.BLACK:
            return board.WHITE
        return board.BLACK

    def parse_move_text(main_board, move, support_analysis):
        move = data.strip()
        analysis = None
        if support_analysis:
            # parse and validate analyze info
            tokens = move.split(None, 1)
            move = tokens[0]
            if len(tokens) > 1:
                # analysis = re.sub("[^- 0-9a-zA-Z._-]", "", tokens[1])
                try:
                    info = json.loads(tokens[1])
                    analysis = json.dumps(info, indent=None, separators=(",", ":"))
                except:
                    pass
        vertex = board.NULL_VERTEX
        move = move.lower()

        if move == "pass":
            vertex = board.PASS
        elif move == "resign":
            vertex = board.RESIGN
        else:
            x = ord(move[0]) - (ord('A') if ord(move[0]) < ord('a') else ord('a'))
            y = int(move[1:]) - 1
            vertex = main_board.get_vertex(x,y)
        return move, vertex, analysis


    time_lefts = dict()
    time_lefts[board.BLACK] = setting["main_time"]
    time_lefts[board.WHITE] = setting["main_time"]

    players = dict()
    players[board.BLACK] = black
    players[board.WHITE] = white

    main_board = board.Board(setting["board_size"], setting["komi"])
    result_status = dict()

    while True:
        to_move_player = players[board.to_move]

        clock_time = time.time()
        time_left = time_lefts[board.to_move]
        rep = to_move_player.send_and_receive(
                  "genmove {} {}".format(
                      color_to_char(board.to_move),
                      time_left
                  )
              )
        time_left -= (time.time() - clock_time)
        if time_left < 0:
            result_status["winner"] = get_opp_color(board.to_move)
            result_status["type"] = "timeout"
            break

        time_lefts[board.to_move] = time_left

        move, vertex, analysis = parse_move_text(
                                     main_board,
                                     rep,
                                     to_move_player.support_analysis
                                 )

        if vertex == board.RESIGN:
            result_status["winner"] = get_opp_color(board.to_move)
            result_status["type"] = "resign"
            break

        if not main_board.legal(vertex):
            result_status["winner"] = get_opp_color(board.to_move)
            result_status["type"] = "illegal move"
            break      

        main_board.play(vertex)

        if main_board.num_passes >= 2:
            black_score = main_board.final_score()

            if black_score > 0.001:
                result_status["winner"] = board.BLACK
            elif black_score < -0.001:
                result_status["winner"] = board.WHITE
            else:
                result_status["winner"] = board.EMPTY
            result_status["type"] = "double pass"
            break
    # black.send_and_receive()
    # white.send_and_receive()
    # TODO: should save the SGF file...


def match_loop(ready_queue, finished_queue):
    while True:
        try:
            black, white = ready_queue.get()
        except queue.Empty:
            time.sleep(1)
            continue


        setting = dict()
        setting["main_time"] = DEFAULT_BOARD_SIZE
        setting["board_size"] = DEFAULT_BOARD_SIZE
        setting["komi"] = DEFAULT_KOMI

        # TODO: use the threads....
        play_match_game(black, white, setting)

        finished_queue.put((black, white))

