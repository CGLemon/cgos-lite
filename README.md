# cgos-lite

A simplified [CGOS](https://github.com/zakki/cgos) server.

## Requirements

* python 3.x or above

## Run the Server

    python3 cgos-lite

## Support Command

* ```quit``` : End the server.
* ```match random```: Randomly select two waiting clients for the match game.
* ```match fid (black fid) (white fid)```: Select two waiting clients for the match game with socket id.
* ```show client```: Show the all waiting socket ids and names.
* ```file [filename]```: Read the batched commands from file.

## Configure

Set the value in the ```config.py```

* ```SERVER_PORT``` : The server port.
* ```NUM_WORKERS``` : How main cores do we use.
* ```DEFAULT_MAIN_SECOND``` : The default thinking time if we do not specify a value in the match.
* ```DEFAULT_BOARD_SIZE``` : The default board size if we do not specify a value in the match.
* ```DEFAULT_KOMI``` : The default komi if we do not specify a value in the match.
* ```SGF_DIR_PATH``` : Will save the SGF files under this path.

## TODO

* Support the Jappenese rule.
* Handle the disconnect issue.
* Start the match game from disconnect time.

## LICENSE

The code is released under the MIT, except for board.py and sgf.py, which have specific licenses mentioned in those files.
