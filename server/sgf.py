# The MIT License
#
# Copyright (C) 2009 Christian Nentwich and contributors
# Copyright (c) 2022 Kensuke Matsuzaki
# Copyright (c) 2023 Hung-Zhe Lin
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import json

def make_sgf(
    board_size,
    komi,
    black_name,
    white_name,
    main_time,
    date,
    history,
    result
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
    sgf += "PB[{black}]PW[{white}]DT[{date}]".format(
               black=black_name,
               white=white_name,
               date=date
           )
    if result is not None:
        sgf += "RE[{res}]\n".format(res=result)
    else:
        sgf += "\n"

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
