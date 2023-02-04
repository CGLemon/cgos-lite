# cgos-lite

A simplified CGOS server.

## Requirements

* python 3.x or above

## Support Command

* ```quit``` : End the server
* ```match random```: Randomly select two waiting clients for the match game.
* ```match (black fid) (white fid)```: Select two waiting clients for the match game with socket id.
* ```show clients```: Show the all socket id.

## Configure

* ```SERVER_PORT``` : The server port.
* ```NUM_WORKERS``` : How main cores do we use.
* ```DEFAULT_MAIN_SECOND``` : The default thinking time if we do not specify a value in the match.
* ```DEFAULT_BOARD_SIZE``` : The default board size if we do not specify a value in the match.
* ```DEFAULT_KOMI``` : The default komi if we do not specify a value in the match.
* ```SGF_DIR_PATH``` : Will save the SGF files under this path.



