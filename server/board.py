# The MIT License
#
# Copyright (c) 2018 Yu Yamaguchi
# Copyright (c) 2022-2023 Hung-Zhe Lin
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

import numpy as np
import copy

BOARD_SIZE = 19
KOMI = 7.5

BLACK = 0
WHITE = 1
EMPTY = 2
INVLD = 3

NUM_VERTICES = (BOARD_SIZE+2) ** 2 # max vertices number
NUM_INTESECTIONS = BOARD_SIZE ** 2 # max intersections number

PASS = -1  # pass
RESIGN = -2 # resign
NULL_VERTEX = NUM_VERTICES+1 # invalid position

class StoneLiberty(object):
    def __init__(self):
        self.lib_cnt = NULL_VERTEX  # liberty count
        self.v_atr = NULL_VERTEX  # liberty position if in atari
        self.libs = set()  # set of liberty positions

    def clear(self):
        # Reset itself.
        self.lib_cnt = NULL_VERTEX
        self.v_atr = NULL_VERTEX
        self.libs.clear()

    def set(self):
        # Set one stone.
        self.lib_cnt = 0
        self.v_atr = NULL_VERTEX
        self.libs.clear()

    def add(self, v):
        # Add liberty at v.
        if v not in self.libs:
            self.libs.add(v)
            self.lib_cnt += 1
            self.v_atr = v

    def sub(self, v):
        # Remove liberty at v.
        if v in self.libs:
            self.libs.remove(v)
            self.lib_cnt -= 1

    def merge(self, other):
        # Merge itself with another stone.
        self.libs |= other.libs
        self.lib_cnt = len(self.libs)
        if self.lib_cnt == 1:
            for lib in self.libs:
                self.v_atr = lib

'''
 What is the vertex? Vertex is not real board position. It is mail-box position. For example,
 We set the board size to 5. The real board looks like

           a b c d e
        1  . . . . .
        2  . . . . .
        3  . . . . .
        4  . . . . .
        5  . . . . .

 We define the coordinate as index, from a1 to e5. There is some problem to shife the index. The
 shift operation may out of the board. For example, we want to find all positions of adjacent a1
 index. There are two positions out of the board. One way to deal with it is to check out the
 boundary. Another fast way to deal with it is mail-box struct. Here is the mail-box looks like

           a b c d e
         - - - - - - -
       1 - . . . . . -
       2 - . . . . . -
       3 - . . . . . -
       4 - . . . . . -
       5 - . . . . . -
         - - - - - - -

 The board size is changed from 5 to 7. We define the new coordinate as vertex. With mail-box,
 we don't need to waste time to check out the boundary any more. Notice that '-' is out of board
 position.

'''

class Board(object):
    def __init__(self, board_size=BOARD_SIZE, komi=KOMI):
        self.state = np.full(NUM_VERTICES, INVLD) # positions state
        self.sl = [StoneLiberty() for _ in range(NUM_VERTICES)]  # stone liberties
        self.reset(board_size, komi)

    def reset(self, board_size, komi):
        # Initialize all board data with current board size and komi.

        self.board_size = min(board_size, BOARD_SIZE)
        self.num_intersections = self.board_size ** 2
        self.num_vertices = (self.board_size+2) ** 2
        self.komi = komi
        ebsize = board_size+2
        self.dir4 = [1, ebsize, -1, -ebsize]
        self.diag4 = [1 + ebsize, ebsize - 1, -ebsize - 1, 1 - ebsize]

        for vtx in range(self.num_vertices):
            self.state[vtx] = INVLD  # set invalid for out border

        for idx in range(self.num_intersections):
            self.state[self.index_to_vertex(idx)] = EMPTY  # set empty for intersetions

        '''
        self.id, self,next, self.stones are basic data struct for strings. By
        these structs, we can search a whole string more fast. For exmple, we
        have the boards looks like
        
        board position
           a b c d e
        1| . . . . .
        2| . x x x .
        3| . . . . .
        4| . x x . .
        5| . . . . .
        
        vertex position
           a  b  c  d  e
        1| 8  9  10 11 12
        2| 15 16 17 18 19
        3| 22 23 24 25 26
        4| 29 30 31 32 33
        5| 36 37 38 39 40

        self.id
           a  b  c  d  e
        1| .  .  .  .  .
        2| .  16 16 16 .
        3| .  .  .  .  .
        4| .  30 30 .  .
        5| .  .  .  .  .

        self.next
           a  b  c  d  e
        1| .  .  .  .  .
        2| .  17 18 16 .
        3| .  .  .  .  .
        4| .  31 30 .  .
        5| .  .  .  .  .

        self.stones
           a  b  c  d  e
        1| .  .  .  .  .
        2| .  3  .  .  .
        3| .  .  .  .  .
        4| .  2  .  .  .
        5| .  .  .  .  .

        If we want to search the string 16, just simply start from its
        id (the string parent vertex). The pseudo code looks like
        
        start_pos = id[vertex]
        next_pos = start_pos
        {
            next_pos = next[next_pos]
        } while(next_pos != start_pos)

        '''

        self.id = np.arange(NUM_VERTICES)  # the id(parent vertex) of string
        self.next = np.arange(NUM_VERTICES)  # next position in the same string
        self.stones = np.zeros(NUM_VERTICES) # the string size

        for i in range(NUM_VERTICES):
            self.sl[i].clear() # clear liberties

        self.num_passes = 0 # number of passes played.
        self.ko = NULL_VERTEX  # illegal position due to Ko
        self.to_move = BLACK  # black
        self.move_num = 0  # move number
        self.last_move = NULL_VERTEX  # last move
        self.removed_cnt = 0  # removed stones count
        self.history = [] # history board positions.

    def copy(self):
        # Deep copy the board to another board. But they will share the same
        # history board positions.

        b_cpy = Board(self.board_size, self.komi)
        b_cpy.state = np.copy(self.state)
        b_cpy.id = np.copy(self.id)
        b_cpy.next = np.copy(self.next)
        b_cpy.stones = np.copy(self.stones)
        for i in range(NUM_VERTICES):
            b_cpy.sl[i].lib_cnt = self.sl[i].lib_cnt
            b_cpy.sl[i].v_atr = self.sl[i].v_atr
            b_cpy.sl[i].libs |= self.sl[i].libs

        b_cpy.num_passes = self.num_passes
        b_cpy.ko = self.ko
        b_cpy.to_move = self.to_move
        b_cpy.move_num = self.move_num
        b_cpy.last_move = self.last_move
        b_cpy.removed_cnt = self.removed_cnt

        for h in self.history:
            b_cpy.history.append(h)
        return b_cpy

    def _remove(self, v):
        # Remove a string including v.

        v_tmp = v
        removed = 0
        while True:
            removed += 1
            self.state[v_tmp] = EMPTY  # set empty
            self.id[v_tmp] = v_tmp  # reset id
            for d in self.dir4:
                nv = v_tmp + d
                # Add liberty to neighbor strings.
                self.sl[self.id[nv]].add(v_tmp)
            v_next = self.next[v_tmp]
            self.next[v_tmp] = v_tmp
            v_tmp = v_next
            if v_tmp == v:
                break  # Finish when all stones are removed.
        return removed

    def _merge(self, v1, v2):
        '''
        board position
           a  b  c  d  e
        1| .  .  .  .  .
        2| .  x  x  x  .
        3| . [x] .  .  .
        4| .  x  .  .  .
        5| .  .  .  .  .

        Merge two strings...
        
            [before]        >>         [after]

        self.id
           a  b  c  d  e             a  b  c  d  e
        1| .  .  .  .  .          1| .  .  .  .  .
        2| .  16 16 16 .          2| .  16 16 16 .
        3| .  30 .  .  .    >>    3| .  16 .  .  .
        4| .  30 .  .  .          4| .  16 .  .  .
        5| .  .  .  .  .          5| .  .  .  .  .

        self.next
           a  b  c  d  e             a  b  c  d  e
        1| .  .  .  .  .          1| .  .  .  .  .
        2| .  17 18 16 .          2| .  30 18 16 .
        3| .  30 .  .  .    >>    3| .  17 .  .  .
        4| .  23 .  .  .          4| .  23 .  .  .
        5| .  .  .  .  .          5| .  .  .  .  .

        self.stones
           a  b  c  d  e             a  b  c  d  e
        1| .  .  .  .  .          1| .  .  .  .  .
        2| .  3  .  .  .          2| .  5  .  .  .
        3| .  .  .  .  .    >>    3| .  .  .  .  .
        4| .  2  .  .  .          4| .  .  .  .  .
        5| .  .  .  .  .          5| .  .  .  .  .

        '''

        # Merge string including v1 with string including v2.

        id_base = self.id[v1]
        id_add = self.id[v2]

        # We want the large string merges the small string.
        if self.stones[id_base] < self.stones[id_add]:
            id_base, id_add = id_add, id_base  # swap

        self.sl[id_base].merge(self.sl[id_add])
        self.stones[id_base] += self.stones[id_add]

        v_tmp = id_add
        while True:
            self.id[v_tmp] = id_base  # change id to id_base
            v_tmp = self.next[v_tmp]
            if v_tmp == id_add:
                break
        # Swap next id for circulation.
        self.next[v1], self.next[v2] = self.next[v2], self.next[v1]

    def _place_stone(self, v):
        # Play a stone on the board and try to merge itself with adjacent strings.

        # Set one stone to the board and prepare data.
        self.state[v] = self.to_move
        self.id[v] = v
        self.stones[v] = 1
        self.sl[v].set()

        for d in self.dir4:
            nv = v + d
            if self.state[nv] == EMPTY:
                self.sl[self.id[v]].add(nv)  # Add liberty to itself.
            else:
                self.sl[self.id[nv]].sub(v)  # Remove liberty from opponent's string.

        # Merge the stone with my string.
        for d in self.dir4:
            nv = v + d
            if self.state[nv] == self.to_move and self.id[nv] != self.id[v]:
                self._merge(v, nv)

        # Remove the opponent's string.
        self.removed_cnt = 0
        for d in self.dir4:
            nv = v + d
            if self.state[nv] == int(self.to_move == 0) and \
                    self.sl[self.id[nv]].lib_cnt == 0:
                self.removed_cnt += self._remove(nv)

    def legal(self, v):
        # Reture true if the move is legal.

        if v == PASS:
            # The pass move is always legal in any condition.
            return True
        elif v == self.ko or self.state[v] != EMPTY:
            # The move is ko move.
            return False

        stone_cnt = [0, 0]
        atr_cnt = [0, 0] # atari count
        for d in self.dir4:
            nv = v + d
            c = self.state[nv]
            if c == EMPTY:
                return True
            elif c <= 1: # The color must be black or white
                stone_cnt[c] += 1
                if self.sl[self.id[nv]].lib_cnt == 1:
                    atr_cnt[c] += 1

        return (atr_cnt[int(self.to_move == 0)] != 0 or # That means we can eat other stones.
                atr_cnt[self.to_move] < stone_cnt[self.to_move]) # That means we have enough liberty to live.

    def play(self, v):
        # Play the move and update board data if the move is legal.

        if not self.legal(v):
            return False
        else:
            if v == PASS:
                # We should be stop it if the number of passes is bigger than 2.
                # Be sure to check the number of passes before playing it.
                self.num_passes += 1
                self.ko = NULL_VERTEX
            else:
                self._place_stone(v)
                id = self.id[v]
                self.ko = NULL_VERTEX
                if self.removed_cnt == 1 and \
                        self.sl[id].lib_cnt == 1 and \
                        self.stones[id] == 1:
                    # Set the ko move if the last move only captured one and was surround
                    # by opponent's stones.
                    self.ko = self.sl[id].v_atr
                self.num_passes = 0

        self.last_move = v
        self.to_move = int(self.to_move == 0) # switch side
        self.move_num += 1

        # Push the current board positions to history.
        self.history.append(copy.deepcopy(self.state))

        return True

    def _compute_reach_color(self, color):
        # This is simple BFS algorithm to compute evey reachable vertices.

        queue = []
        reachable = 0
        buf = [False] * NUM_VERTICES

        # Collect my positions.
        for v in range(NUM_VERTICES):
            if self.state[v] == color:
                reachable += 1
                buf[v] = True
                queue.append(v)

        # Now start the BFS algorithm to search all reachable positions.
        while len(queue) != 0:
            v = queue.pop(0)
            for d in self.dir4:
                nv = v + d
                if self.state[nv] == EMPTY and buf[nv] == False:
                    reachable += 1
                    queue.append(nv)
                    buf[nv] = True
        return reachable

    def final_score(self):
        # Scored the board area with Tromp-Taylor rule.
        return self._compute_reach_color(BLACK) - self._compute_reach_color(WHITE) - self.komi

    def get_x(self, v):
        # vertex to x
        return v % (self.board_size+2) - 1

    def get_y(self, v):
        # vertex to y
        return v // (self.board_size+2) - 1

    def get_vertex(self, x, y):
        # x, y to vertex
        return (y+1) * (self.board_size+2) + (x+1)
        
    def get_index(self, x, y):
        # x, y to index
        return y * self.board_size + x

    def vertex_to_index(self, v):
        # vertex to index
        return self.get_index(self.get_x(v), self.get_y(v))
        
    def index_to_vertex(self, idx):
        # index to vertex
        return self.get_vertex(idx % self.board_size, idx // self.board_size)

    def vertex_to_text(self, vtx):
        # vertex to GTP move

        if vtx == PASS:
            return "pass"
        elif vtx == RESIGN:
            return "resign"
        
        x = self.get_x(vtx)
        y = self.get_y(vtx)
        offset = 1 if x >= 8 else 0 # skip 'I'
        return "".join([chr(x + ord('A') + offset), str(y+1)])

    def superko(self):
        # Return true if the current position is superko.

        curr_hash = hash(self.state.tostring())
        s = len(self.history)
        for p in range(s-1):
            h = self.history[p]
            if hash(h.tostring()) == curr_hash:
                return True
        return False

    def __str__(self):
        def get_xlabel(bsize):
            X_LABELS = "ABCDEFGHJKLMNOPQRST"
            line_str = "  "
            for x in range(bsize):
                line_str += " " + X_LABELS[x] + " "
            return line_str + "\n"
        out = str()
        out += get_xlabel(self.board_size)

        for y in range(0, self.board_size)[::-1]:  # 9, 8, ..., 1
            line_str = str(y+1) if y >= 9 else " " + str(y+1)
            for x in range(0, self.board_size):
                v = self.get_vertex(x, y)
                x_str = " . "
                color = self.state[v]
                if color <= 1:
                    stone_str = "O" if color == WHITE else "X"
                    if v == self.last_move:
                        x_str = "[" + stone_str + "]"
                    else:
                        x_str = " " + stone_str + " "
                line_str += x_str
            line_str += str(y+1) if y >= 10 else " " + str(y+1)
            out += (line_str + "\n")

        out += get_xlabel(self.board_size)
        return out + "\n"
