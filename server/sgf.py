import json

def make_sgf(
    board_size,
    komi,
    black_name,
    white_name,
    main_time,
    date,
    result,
    history
):
    def escape_text(s):
        sgf_special_chars = str.maketrans(
            {
                "]": "\\]",
                "\\": "\\\\",
            }
        )
        return s.translate(sgf_special_chars)

    to_move = 0
    colstr = ["B", "W"]

    sgf = "(;GM[1]FF[4]CA[UTF-8]\n"
    sgf += "RU[{rule}]SZ[{boardsize}]KM[{komi}]TM[{t}]\n".format(
               rule="Chinese",
               boardsize=board_size,
               komi=komi,
               t=main_time
           )
    sgf += "PB[{black}]PW[{white}]DT[{date}]RE[{res}]\n".format(
               black=black_name,
               white=white_name,
               date=date,
               res=result
           )

    i = 0
    for move, time_left, analysis in history:
        if move.lower() == "pass":
            sgf += ";{}[{}]{}L[{}]".format(
                       colstr[to_move],
                       "", # tt or empty
                       colstr[to_move],
                       time_left
                   )
        elif move.lower() == "resign":
            pass
        else:
            ccs = ord(move.lower()[0])
            if ccs > 104:
                ccs -= 1
            rrs = int(move[1:])
            rrs = (board_size - rrs) + 97
            sgf += ";{}[{}{}]{}L[{}]".format(
                       colstr[to_move],
                       chr(ccs),
                       chr(rrs),
                       colstr[to_move],
                       time_left
                   )

        if analysis is not None:
            i = 0
            sgf += "CC[{}]".format(
                       escape_text(analysis)
                   )
            v = json.loads(analysis)
            if "comment" in v:
                c = v["comment"]
                sgf += "C[{}]".format(
                           escape_text(c)
                       )
            sgf += "\n"
            i = 0

        if i > 7:
            sgf += "\n"
            i = 0

        i += 1
        to_move = to_move ^ 1

    sgf += ")\n"
    return sgf
