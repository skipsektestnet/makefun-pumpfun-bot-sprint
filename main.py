# Whale-Follow Rider: a paper trading bot for the Pump.fun Bot Sprint.
# Run by the grader as `python3 -P -s /bot/main.py` (Python 3.13, stdlib only).
# The strategy lives in strategy.py; the SDK shim is the kit's
# sdk/python/makefun_bot.py, vendored byte for byte in vendor/. The harness
# sends a hello first, then one batch of chain events per slot, and the bot
# answers each batch with its orders for that slot.

import os
import sys

# -P leaves the script's own directory off sys.path, so put it back (for
# strategy.py) along with vendor/ (for the SDK shim).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "vendor"))

import makefun_bot  # noqa: E402  (after the sys.path lines)
from strategy import create_bot  # noqa: E402

bot = create_bot()

if __name__ == "__main__":
    makefun_bot.run(bot.on_batch)
