import time
import config
import threading
import datetime
import queue
import json
import os

import board as brd
from sgf import make_sgf

class ClientStatus:
    def __init__(self):
        self.name = None
        self.sock = None
        self._sock_file = None
        self.fid = None
        self.support_analysis = False

    def setup_socket(self, sock):
        if self.sock is not None:
            self.close()
            self.sock = None
        else:
            self.sock = sock
            self.fid = sock.fileno()

        self.create_sockfile()
        msg = self.request_protocol()

        if msg[0:2] == "e1":
            parameters = msg.split()
            self.support_analysis = "genmove_analyze" in parameters
        else:
            raise Exception("Do not soppurt this client version.")

        self.name = self.request_username().strip()
        msg = self.request_password() # not used...
        self.close_sockfile()

    def request_info(self, info):
        self.send("info {}".format(info))

    def request_protocol(self):
        return self.send_and_receive("protocol genmove_analyze")

    def request_username(self):
        return self.send_and_receive("username")

    def request_password(self):
        return self.send_and_receive("password")

    def request_setup(self, board_size,
                            komi,
                            main_time_msec,
                            player_a_name,
                            player_b_name):
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
        param = "{} {} {}".format(
                    color, move, time_left_msec
                )
        return self.send("play {}".format(param))

    def request_genmove(self, color, time_left_msec):
        param = "{} {}".format(
                    color, time_left_msec
                )
        return self.send_and_receive("genmove {}".format(param))

    def request_gameover(self, date, result, err):
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
            raise Exception("Can not close the client socket.")

    def create_sockfile(self):
        self.close_sockfile()
        self._sock_file = self.sock.makefile("rw", encoding="utf-8")

    def close_sockfile(self):
        if self._sock_file is not None:
            self._sock_file.close()
        self._sock_file = None

    def receive(self):
        msg = None
        try:
            msg = self._sock_file.readline()
        except:
            raise Exception("Can not read massage from client.")
        return msg

    def send(self, msg):
        try:
            self._sock_file.write("{}\n".format(msg))
            self._sock_file.flush()
        except:
            raise Exception("Can not send massage to client.")

    def send_and_receive(self, msg):
        self.send(msg)
        return self.receive()

def play_match_game(black, white, game_id, setting):
    def color_to_char(c):
        if c == brd.BLACK:
            return 'b'
        return 'w'

    def get_opp_color(c):
        if c == brd.BLACK:
            return brd.WHITE
        return brd.BLACK

    def move_to_vertex(board, move, support_analysis):
        move = move.strip()
        analysis = None
        if support_analysis:
            # parse and validate analyze info
            tokens = move.split(None, 1)
            move = tokens[0]
            if len(tokens) > 1:
                try:
                    info = json.loads(tokens[1])
                    analysis = json.dumps(info, indent=None, separators=(",", ":"))
                except:
                    pass
        vertex = brd.NULL_VERTEX
        move = move.lower()

        if move == "pass":
            vertex = brd.PASS
        elif move == "resign":
            vertex = brd.RESIGN
        else:
            x = ord(move[0]) - (ord('A') if ord(move[0]) < ord('a') else ord('a'))
            y = int(move[1:]) - 1
            if x >= 8:
                x -= 1
            vertex = board.get_vertex(x,y)
        return move, vertex, analysis

    # Initialize some basic data.
    time_lefts = {
        brd.BLACK : setting["main_time"],
        brd.WHITE : setting["main_time"]
    }
    players = {
        brd.BLACK : black,
        brd.WHITE : white
    }

    history = list() # move, time_left and analysis

    for player in players.values():
        player.create_sockfile()
        player.request_setup(
            setting["board_size"],
            setting["komi"],
            setting["main_time"] * 1000,
            players[brd.WHITE].name,
            players[brd.BLACK].name
        )

    ctime = datetime.datetime.now(datetime.timezone.utc)
    board = brd.Board(setting["board_size"], setting["komi"])
    result_status = dict()

    try:
        while True:
            side_to_move = board.to_move
            opp_to_move = get_opp_color(board.to_move)
            to_move_player = players[side_to_move]

            # Request engine the to do the genmove command.
            clock_time = time.time()
            time_left = time_lefts[side_to_move]
            rep = to_move_player.request_genmove(
                      color_to_char(side_to_move),
                      int(time_left * 1000)
                  )
            time_left -= (time.time() - clock_time)

            if time_left < 0:
                # Game ended by time out.
                winner = opp_to_move
                result_status["winner"] = winner
                result_status["type"] = "time out"
                result_status["info"] = "{}+Time".format(
                                            color_to_char(winner).upper()
                                        )
                break

            time_lefts[side_to_move] = time_left
            move, vertex, analysis = move_to_vertex(
                                         board,
                                         rep,
                                         to_move_player.support_analysis
                                     )

            if vertex == brd.RESIGN:
                # Game ended by resign move.
                winner = opp_to_move
                result_status["winner"] = winner
                result_status["type"] = "resign"
                result_status["info"] = "{}+Resign".format(
                                            color_to_char(winner).upper()
                                        )
                break  

            is_legal = board.play(vertex)

            if not is_legal or (vertex != brd.PASS and board.superko()):
                # Game ended by illegal move.
                winner = opp_to_move
                result_status["winner"] = winner
                result_status["type"] = "illegal move"
                result_status["info"] = "{}+Illegal".format(
                                            color_to_char(winner).upper()
                                        )
                break    

            history.append((move, int(time_left), analysis))


            time_left = time_lefts[opp_to_move]
            opp_player = players[opp_to_move]
            opp_player.request_play(
                color_to_char(side_to_move),
                board.vertex_to_text(vertex),
                int(time_left * 1000)
            )

            if board.num_passes >= 2:
                # Game ended by double pass.
                black_score = board.final_score()

                if black_score > 0.001:
                    winner = brd.BLACK
                elif black_score < -0.001:
                    winner = brd.WHITE
                else:
                    winner = brd.EMPTY
                result_status["winner"] = winner
                result_status["type"] = "double pass"

                if winner == brd.EMPTY:
                    result_status["info"] = "0"
                else:
                    result_status["info"] = "{}+{}".format(
                                                color_to_char(winner).upper(),
                                                abs(black_score)
                                            )
                break
    except:
        result_status["winner"] = brd.EMPTY
        result_status["type"] = "no result"
        result_status["info"] = "0"

    date = ctime.strftime("%Y-%m-%d")
    result = result_status["info"]
    err = str()

    black.request_gameover(date, result, err)
    white.request_gameover(date, result, err)

    for player in players.values():
        player.close_sockfile()


    # Save the sgf file.
    sgf = make_sgf(
              board.board_size,
              board.komi,
              black.name,
              white.name,
              setting["main_time"],
              date,
              result,
              history
          )

    sgf_path = os.path.join(*config.SGF_DIR_PATH)
    if not os.path.isdir(sgf_path):
        os.mkdir(sgf_path)

    with open(os.path.join(sgf_path, "{}.sgf".format(game_id)), 'w') as f:
        f.write(sgf)


def match_loop(ready_queue, finished_queue):
    match_threads = dict()

    while True:
        finished_ids = list()
        for k, v in match_threads.items():
            # Collect all finished match games.
            t, _, _, _ = v
            if not t.is_alive():
                finished_ids.append(k)

        for i in finished_ids:
            # The match game is game over. Push the play
            # back to main pooling.
            v = match_threads.pop(i)
            t, b, w, i = v
            t.join()

            task = {
                "black" : b,
                "white" : w,
                "id"    : i
            }
            finished_queue.put(task)

        # More sleep if there are more running threads because
        # we want to raise probability of the process with low
        # running threads to get the match task.
        time.sleep(min(2, 0.1 + 0.1 * len(match_threads)))

        try:
            task = ready_queue.get(block=True, timeout=0)
            black = task["black"] # black player
            white = task["white"] # white player
            game_id = task["id"]
        except queue.Empty:
            continue


        setting = {
            "main_time"  : task.get("main_time", config.DEFAULT_MAIN_SECOND),
            "board_size" : task.get("board_size", config.DEFAULT_BOARD_SIZE),
            "komi"       : task.get("komi", config.DEFAULT_KOMI)
        }

        t = threading.Thread(
                target=play_match_game,
                args=(black, white, game_id, setting, ),
                daemon=True
            )
        t.start()
        match_threads[t.ident] = (t, black, white, game_id)
