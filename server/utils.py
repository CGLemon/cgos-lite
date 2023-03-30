import os

def check_and_mkdir(path):
    if isinstance(path, str):
        path = path.split(os.sep) # string -> list

    if path[0] == ".":
        path.pop(0)

    curr = "."
    for v in path:
        curr = os.path.join(curr, v)
        if not os.path.isdir(curr):
            os.mkdir(curr)

def get_html_code(wgo_path, sgf_name):
    wgo_js = os.path.join(wgo_path, "wgo.min.js")
    player_js = os.path.join(wgo_path, "wgo.player.min.js")
    wgo_css = os.path.join(wgo_path, "wgo.player.css")
    out = \
        "<!DOCTYPE HTML>" \
        "<html>" \
        "<head>" \
        "<title>SGF viewer</title>" \
        "<script type=\"text/javascript\" src=\"{}\"></script>" \
        "<script type=\"text/javascript\" src=\"{}\"></script>" \
        "<link type=\"text/css\" href=\"{}\" rel=\"stylesheet\"/>" \
        "</head>" \
        "<body>" \
        "<div data-wgo=\"{}\" style=\"width: 700px\">" \
        "Sorry, your browser doesn't support WGo.js. Download the SGF " \
        "<a href=\"{}\">directly</a>." \
        "</div>" \
        "</body>" \
        "</html>".format(
            wgo_js, player_js, wgo_css, sgf_name, sgf_name)
    return out
