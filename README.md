# cgos-lite

A simplified [CGOS](https://github.com/zakki/cgos) server.

## Requirements

* python 3.x or above

## Run the Server

    python3 cgos-lite

## Support Commands

* ```quit``` : End the server.
* ```show client```: Show the status of clients.
* ```match```
    * ```random```
        * Randomly select two waiting clients for match game.
    * ```fid (black fid) (white fid) [optional...]```
        * Select two waiting clients for match game via fids. Other fields are optional.
        * ```bsize```: The game board size.
        * ```komi```: The gama komi.
        * ```mtime```: The game main time in second.
        * ```sgf```: The source of SGF name, starting the match  from it.
        * The sample is like ```match fid 1 2 mtime 900 bsize 19 komi 7.5```.
* ```file [filename]```: Read the batched commands from file.

## Configure

Set these values in the ```config.py```

* ```SERVER_PORT``` : The server port.
* ```NUM_WORKERS``` : How many cores do we use.
* ```DEFAULT_MAIN_SECOND``` : The default thinking time if we do not specify a value in the match.
* ```DEFAULT_BOARD_SIZE``` : The default board size if we do not specify a value in the match.
* ```DEFAULT_KOMI``` : The default komi if we do not specify a value in the match.
* ```SGF_DIR_PATH``` : Will save the SGF files under this path.

## TODO

* Support the Jappenese rule.
* GUI for the user.

## LICENSE

The code is released under the MIT, except for board.py and sgf.py, which have specific licenses mentioned in those files.
