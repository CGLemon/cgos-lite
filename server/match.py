import time
import config
import threading
import datetime
import queue
import json
import os

import board as brd
from sgf import make_sgf, parse_sgf
from client import ClientSocketError
from utils import check_and_mkdir, get_html_code

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
        # Parse and validate analyze info.
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

def write_sgf_and_html(
    setting,
    names,
    date,
    move_history,
    result,
    base_name
):
    black_name, white_name = names
    sgf_store_path = os.path.join(
        *config.DATA_DIR_ROOT, "sgf", setting["store"])

    if os.path.isdir(sgf_store_path):
        # Save the SGF file.
        sgf_name = "{}.sgf".format(base_name)
        sgf = make_sgf(
                  setting["board_size"],
                  setting["komi"],
                  black_name,
                  white_name,
                  setting["main_time"],
                  date,
                  move_history,
                  result
              )
        sgf_full_name = os.path.join(sgf_store_path, sgf_name)
        with open(sgf_full_name, 'w') as f:
            f.write(sgf)

        html_store_path = os.path.join(
            *config.DATA_DIR_ROOT, "html", setting["store"])
        if os.path.isdir(html_store_path) and config.WGO_PATH is not None:
            html_name = "{}.html".format(base_name)

            back_count = 0
            for v in setting["store"].split(os.sep):
                # Assume there is no ".." symbol.
                if v != ".":
                    back_count += 1

            back_path = "."
            for _ in range(back_count+1):
                # Back to data directory root.
                back_path = os.path.join(back_path, "..")

            # Rewrite the WGO and SGF path in the HTML file.
            sgf_name_in_html = os.path.join(
                back_path, "sgf", setting["store"], sgf_name)
            wgo_path_in_html = os.path.join(back_path, config.WGO_PATH)

            html_full_name = os.path.join(html_store_path, html_name)
            if not os.path.isfile(html_full_name):
                # Only wrtie the HTML file once.
                with open(html_full_name, 'w') as f:
                    f.write(get_html_code(wgo_path_in_html, sgf_name_in_html))
        return True
    return False

def play_match_game(game_id, black, white, setting):
    # Play a match game and save the SGF file. The client may
    # crash here. We detect it and guarantee that the client can
    # return back safely. The socket is not closed here when
    # crashing. The master will close it later.

    # Initialize some basic data.
    time_lefts = {
        brd.BLACK : setting["main_time"],
        brd.WHITE : setting["main_time"]
    }
    players = {
        brd.BLACK : black,
        brd.WHITE : white
    }

    # TODO: Add support for Chinese rule and Japanese rule.
    rule = setting["rule"]
    should_superko = rule == "chinese-like"

    # We only record the starting time in order to fix
    # the output file name.
    date = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

    # 
    sgf_clock_time = time.time()

    # The store path and SGF name.
    base_name = "{}-{}(B)-{}(W)-g{}".format(date, black.name, white.name, game_id)

    move_history = list() # It contains (move, time_left and analysis).

    # Try to read the SGF file. Should start the game from
    # it if the source is not None.
    sgf_source = setting.get("sgf", None)
    if (sgf_source is not None) and (os.path.isfile(sgf_source)):
        with open(sgf_source, 'r') as f:
            sgf = f.read().strip()
            board_size, komi, move_history = parse_sgf(sgf)
            # Rewrite the game setting.
            setting["board_size"] = board_size
            setting["komi"] = komi

    board = brd.Board(setting["board_size"], setting["komi"])
    result_status = dict()

    try:
        for player in players.values():
            # Request each clients to initialize the game also
            # create new socket file.
            player.create_sockfile()
            player.request_setup(
                setting["board_size"],
                setting["komi"],
                setting["main_time"] * 1000,
                players[brd.WHITE].name,
                players[brd.BLACK].name
            )

        while len(move_history) > board.move_num:
            # Play the moves from SGF file.
            side_to_move = board.to_move
            to_move_player = players[side_to_move]
            move, time_left, _ = move_history[board.move_num] 

            move, vertex, _ = move_to_vertex(
                                  board, move, False
                              )

            # Always assuem the move is legel.
            board.play(vertex)

            # Both clients should play the move.
            for player in players.values(): 
                player.request_play(
                    color_to_char(side_to_move),
                    board.vertex_to_text(vertex),
                    int(time_left * 1000)
                )

        while True:
            side_to_move = board.to_move
            opp_to_move = get_opp_color(board.to_move)
            to_move_player = players[side_to_move]

            # Request the engine to genmove the next move.
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

            # Parse the move and analysis string.
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

            if not is_legal or \
                (vertex != brd.PASS and \
                     not should_superko and board.superko()):
                # Game ended by illegal move.
                winner = opp_to_move
                result_status["winner"] = winner
                result_status["type"] = "illegal move"
                result_status["info"] = "{}+Illegal".format(
                                            color_to_char(winner).upper()
                                        )
                break    

            move_history.append((move, int(time_left), analysis))

            # Try to save game result into SGF file after updating
            # the move_history. Failed to save it if the client play
            # the move too quick. 
            if time.time() - sgf_clock_time > 5:
                if write_sgf_and_html(
                       setting,
                       (black.name, white.name), 
                       date,
                       move_history,
                       None,
                       base_name):
                    sgf_clock_time = time.time()

            # Request the opponent to play the move.
            time_left = time_lefts[opp_to_move]
            opp_player = players[opp_to_move]
            opp_player.request_play(
                color_to_char(side_to_move),
                board.vertex_to_text(vertex),
                int(time_left * 1000)
            )

            if board.num_passes >= 2:
                # Game ended by double pass. Now score
                # the final position.

                if rule == "chinese-like":
                    result_status["type"] = "double pass"
                    black_score = board.final_score()
                else:
                    # Invalid rules.
                    result_status["type"] = "invalid rule"
                    black_score = 0

                if black_score > 0.001:
                    winner = brd.BLACK
                elif black_score < -0.001:
                    winner = brd.WHITE
                else:
                    winner = brd.EMPTY
                result_status["winner"] = winner

                if winner == brd.EMPTY:
                    result_status["info"] = "0"
                else:
                    result_status["info"] = "{}+{}".format(
                                                color_to_char(winner).upper(),
                                                abs(black_score)
                                            )
                break
    except:
        # TODO: Catch the error and write it into the SGF file.
        result_status["winner"] = brd.EMPTY
        result_status["type"] = "socket error"
        result_status["info"] = "0"

    result = result_status["info"]
    err = str()

    for player in players.values():
        try:
           # Send the last request to server here in order
           # to check whether the socket is still connected.
           player.request_gameover(date, result, err)
        except ClientSocketError as e:
            pass

    # Close the socket file because the we can not push socket file
    # onto process queue.
    for player in players.values():
        try:
           player.close_sockfile()
        except ClientSocketError as e:
            pass

    # Always save the SGF file before leaving.
    write_sgf_and_html(
        setting,
        (black.name, white.name), 
        date,
        move_history,
        result,
        base_name)

def match_loop(process_id, ready_queue, finished_queue):
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
            t, i, b, w = v
            t.join()

            task = {
                "black" : b,
                "white" : w,
                "gid"   : i,
                "pid"   : process_id
            }
            finished_queue.put(task)

        try:
            task = ready_queue.get(block=True, timeout=0.1)
            if task["pid"] != process_id:
                # Not correct process id. Reture it to finished
                # queue.
                finished_queue.put(task)
            black = task["black"] # black player
            white = task["white"] # white player
            game_id = task["gid"] # game id
        except queue.Empty:
            continue

        # TODO: Add support for more task type.

        setting = {
            "main_time"  : task.get("main_time", config.DEFAULT_MAIN_SECOND),
            "board_size" : task.get("board_size", config.DEFAULT_BOARD_SIZE),
            "komi"       : task.get("komi", config.DEFAULT_KOMI),
            "sgf"        : task.get("sgf", None),
            "store"      : task.get("store", config.DEFAULT_STORE_DIR),
            "rule"       : task.get("rule", "chinese-like")
        }

        # New game is starting. Each threads hold one game. The threads
        # will be released after the gameover.
        t = threading.Thread(
                target=play_match_game,
                args=(game_id, black, white, setting, ),
                daemon=True
            )
        t.start()
        match_threads[t.ident] = (t, game_id, black, white)
