import re
import random

from cloudbot.event import EventType
from cloudbot import hook

takbirs = [
    "الله أكبر",
    "Allahu akbar!",
    "اَللّٰهُ أَكْبَر",
    "ALLAHU AKBAR!"
    ]

opt_in = ['#islam', '#islam2', '#islamadmins', '#sy']

takbir_re = re.compile(r"takbir", re.IGNORECASE)

@hook.regex(takbir_re)
def takbir(match, conn, nick, chan, message):
    """
    :type match: re.__Match
    :type conn: cloudbot.client.Client
    :type chan: str
    """
    if chan in opt_in:
        takbir = random.choice(takbirs)
        message(takbir, chan)
