import random

from cloudbot.event import EventType
from cloudbot import hook

neps = [
    "http://i.imgur.com/6gGqRkR.png",
    "http://i.imgur.com/aSG01Ys.png",
    "http://i.imgur.com/6oqb4lt.png",
    "http://i.imgur.com/X0PEM7E.png",
    "http://i.imgur.com/vIZvI7g.png",
    "http://i.imgur.com/1oaJLko.png",
    "http://i.imgur.com/xW2ixtd.jpg",
    "http://i.imgur.com/QjaMYvH.png",
    "http://i.imgur.com/lEx1vzW.jpg",
    "http://i.imgur.com/neLShbu.png",
    "http://i.imgur.com/61EQcvw.png",
    "http://i.imgur.com/mlKgU8Y.png",
    "http://is.gd/m4t64m",
    "http://is.gd/NlW5hK",
    "http://is.gd/1t49BO",
    "http://i.imgur.com/c1kgouO.png",
    "http://i.imgur.com/jTnIxFH.png",
    "http://i.imgur.com/5PUcrdy.png",
    "http://i.imgur.com/joWrNPg.png",
    "http://i.imgur.com/RmwR2FU.jpg",
    "http://i.imgur.com/CMfpZB0.png",
    "http://i.imgur.com/w3zYpPJ.png",
    "http://i.imgur.com/xCD7r0G.png",
    "http://is.gd/ZuZrms"
    ]

opt_in = ['#islam', '#islam2', '#islamadmins', '#sy']

@hook.command
def nep(nick, chan, message):
    if chan in opt_in:
        nep = random.choice(neps)
        message(nep, chan)

