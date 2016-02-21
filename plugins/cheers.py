import re
import random

from cloudbot.event import EventType
from cloudbot import hook

cheers = [
    "OH YEAH!",
    "HOORAH!",
    "HURRAY!",
    "OORAH!",
    "YAY!",
    "*\o/* CHEERS! *\o/*",
    "HOOHAH!",
    "HOOYAH!",
    "HUAH!",
    "♪  ┏(°.°)┛  ┗(°.°)┓ ♬"
    ]

cheer_re = re.compile('\\\\o\/', re.IGNORECASE)

@hook.regex(cheer_re)
def cheer(match, conn, nick, chan, message):
    """
    :type match: re.__Match
    :type conn: cloudbot.client.Client
    :type chan: str
    """
    if chan not in ["#yogscast"]:
        shit = random.choice(cheers)
        message(shit, chan)
