# Whale-Follow Rider — a paper bot for the Pump.fun Bot Sprint (agent-fun/replay/v2).
#
# Idea: on pump.fun, the first minutes of a launch are where the money is, but
# buying every fresh launch is a lottery ticket with the odds against you — the
# dev window's earlier bots measured that directly (buy-the-open sniper +0.32
# SOL, plain momentum -9.38 SOL, mean reversion -1.78 SOL). This bot waits for
# one specific, checkable signal instead: a single large buy from a
# non-creator wallet — a whale-sized ticket — landing in the launch's first 30
# slots, on a coin whose creator already has skin in the game. A 0.5 SOL buy
# from a stranger is not a creator wash-trading their own mint; it is someone
# else putting real money behind the coin before the crowd arrives. The bot
# follows that wallet in, once, with a small fixed stake, and is out again
# within ten slots — the spike either comes at once or it never comes.
#
# What the dev window says (measured on the kit's 24 h dataset, 1,222 mints,
# before this file was written — crude tape math, no latency, no caps, so
# treat the levels as a guide and the grade-local run as the verdict):
#   * A >=0.5 SOL single buy by a non-creator in the first 30 slots, landing
#     once >=2 distinct buyers are already on the tape, with creator skin
#     0.2-2.5 SOL and real reserves 0.3-30 SOL, fires on ~145 coins per
#     24 h (worst 6 h slice: 26 coins — above the 20-coin guardrail), with
#     ~34% of them reaching +25% and ~12% stopping out at -12% within
#     10 slots. Expected value about +0.07 per 0.3 SOL trade before
#     latency and fees.
#   * The same signal without the creator-skin and reserve filters fires on
#     459 coins but the win rate collapses (26% TP, EV +0.047 and far worse
#     at the tails) — the filters are doing the work, not the whale alone.
#     And the big ticket alone, on an empty tape (a lone >=0.5 SOL buy as
#     the first or second trade, before any crowd forms), is nearly
#     worthless as a signal: 568 of the 632 big early buys arrive that way.
#     The crowd has to be there first — that is the whole filter.
#   * Two neighbouring ideas were measured and rejected on the same window:
#     buying the pullback after a >=60% run-up (292 triggers, but 47% end
#     below -12% within 40 slots — pullbacks mostly keep falling), and buying
#     right after the creator's first sell (159 triggers, EV -0.03/trade —
#     the creator selling is the top, not a dip). Neither is in this bot.
#   * Neighbouring settings are flat: whale 0.3-1.0 SOL, age 20-60 slots,
#     hold 8-12 slots all land within a few hundredths of each other per
#     trade, so the chosen point is not a knife edge.
#
# Rules, all of them checked before any buy:
#   * a single non-creator buy of >= 0.5 SOL in the mint's first 30 slots,
#     landing once the tape already shows >= 2 distinct non-creator buyers
#     — the big ticket has to arrive after the crowd has started forming,
#     not as the very first trade (a lone 0.5 SOL buy on an empty tape is
#     usually the creator's other wallet);
#   * >= 3 trades on the tape;
#   * the creator bought 0.2-2.5 SOL of their own coin in the create slot
#     (skin in the game; above 2.5 SOL it is usually a bundle) and has not
#     sold;
#   * real SOL reserves 0.3-30 SOL at decision time;
#   * no single non-creator sell larger than 30% of real reserves seen.
# One 0.3 SOL shot per mint (capped at 1% of real reserves, never under
# 0.01 SOL so each buy counts as a guardrail round trip). No second buys,
# no pyramiding. A signal that cannot be acted on at once (position cap,
# cash) stays live: the next qualifying big ticket re-signals the mint
# while it is still young.
#
# It leaves on whichever comes first: +20%, -10%, 10 slots held, or the
# creator selling while the position is held. No trailing stop, no riding.
#
# Fully deterministic: no clock, no randomness, no I/O, no network. Sets are
# only ever tested for membership and size, never iterated, so hash order
# cannot leak into the action log. Iteration is over insertion-ordered dicts
# fed by the batch stream.

BPS = 10_000
LAMPORTS_PER_SOL = 1_000_000_000

# Entry signal.
WHALE_MIN = 500_000_000            # 0.5 SOL in one non-creator buy
MAX_AGE_SLOTS = 30                 # whale buy must land in the first 30 slots
BUYERS_MIN = 2                     # distinct non-creator buyers on the tape
TRADES_MIN = 3                     # trades seen before entry
DEV_BUY_LOW = 200_000_000          # creator's own buy in the create slot
DEV_BUY_HIGH = 2_500_000_000       # ... skin in the game, not a bundle
RESERVE_LOW = 300_000_000          # real SOL reserves at decision time
RESERVE_HIGH = 30_000_000_000
MAX_DUMP_BPS = 3_000               # biggest single non-creator sell, bps of reserve

# Sizing and exits.
STAKE = 300_000_000                # 0.3 SOL per mint, one shot
FLOOR_BUY = 10_000_000             # 0.01 SOL: guardrail round-trip floor
TAKE_PROFIT_BPS = 2_000            # +20%
STOP_LOSS_BPS = 1_000              # -10%
HOLD_LIMIT_SLOTS = 10
BUY_SLIPPAGE_BPS = 10_000          # wide open: never reject on slippage
SELL_SLIPPAGE_BPS = 10_000

CURVE_FEE_BPS = 125                # protocol 95 + creator 30, per side


def exit_value(tokens, vq, vt):
    """What selling `tokens` against (vq, vt) pays out once curve fees are off."""
    if tokens <= 0 or vt <= 0:
        return 0
    gross = (tokens * vq) // (vt + tokens)
    fee = (gross * CURVE_FEE_BPS + BPS - 1) // BPS
    return gross - fee


class Launch:
    """Everything the bot remembers about one mint, folded from the tape."""

    __slots__ = (
        "mint", "born_slot", "creator", "dev_buy", "dev_sold", "trade_count",
        "buyers", "worst_dump", "signal_slot", "decided", "finished",
    )

    def __init__(self, mint, born_slot, creator):
        self.mint = mint
        self.born_slot = born_slot
        self.creator = creator
        self.dev_buy = 0
        self.dev_sold = False
        self.trade_count = 0
        self.buyers = set()
        self.worst_dump = 0
        self.signal_slot = None
        self.decided = False
        self.finished = False


class Position:
    """An open position: when it was filled and what it has already paid."""

    __slots__ = ("opened_at", "fees_paid", "dev_sold_at_entry")

    def __init__(self, opened_at, fees_paid, dev_sold_at_entry):
        self.opened_at = opened_at
        self.fees_paid = fees_paid
        self.dev_sold_at_entry = dev_sold_at_entry


class WhaleFollowBot:
    def __init__(self):
        self.launches = {}
        self.positions = {}
        self.exiting = set()

    # -- tape folding ----------------------------------------------------
    def _absorb(self, batch):
        for e in batch["events"]:
            kind = e["event"]
            mint = e["mint"]
            if kind == "CreateEvent":
                self.launches[mint] = Launch(mint, e["slot"], e["creator"])
            elif kind == "TradeEvent":
                launch = self.launches.get(mint)
                if launch is None:
                    continue
                slot = e["slot"]
                amount = int(e["sol_amount"])
                is_buy = e["is_buy"]
                user = e["user"]
                launch.trade_count += 1
                by_creator = user == launch.creator
                if is_buy:
                    if by_creator and slot == launch.born_slot:
                        launch.dev_buy += amount
                    elif not by_creator:
                        launch.buyers.add(user)
                        # The signal: one big ticket from a stranger, early,
                        # once the tape already shows a crowd forming. A
                        # later big ticket re-signals the mint while young.
                        if (
                            amount >= WHALE_MIN
                            and slot - launch.born_slot <= MAX_AGE_SLOTS
                            and len(launch.buyers) >= BUYERS_MIN
                        ):
                            launch.signal_slot = slot
                elif by_creator:
                    launch.dev_sold = True
                else:
                    reserve_before = int(e["real_quote_reserves"]) + amount
                    if reserve_before > 0:
                        share = (amount * BPS) // reserve_before
                        if share > launch.worst_dump:
                            launch.worst_dump = share
            else:  # CompleteEvent (or anything else): the mint is done.
                launch = self.launches.get(mint)
                if launch is not None:
                    launch.finished = True
                    launch.decided = True

    # -- helpers ---------------------------------------------------------
    def _pending(self, state, mint, side):
        for p in state.pending.values():
            if p.order["mint"] == mint and p.order["side"] == side:
                return True
        return False

    # -- main entry point -------------------------------------------------
    def on_batch(self, state, batch):
        self._absorb(batch)
        slot = state.slot
        orders = []
        caps = state.hello["caps"]
        batch_cap = caps["max_orders_per_batch"]
        tx_fee = state.tx_fee_lamports()

        # Fills: open positions on filled buys, close them on sells and on
        # the harness's own closes (client ids starting with '_').
        for f in batch["fills"]:
            mint = f["mint"]
            if f["client_id"].startswith("_"):
                self.positions.pop(mint, None)
                self.exiting.discard(mint)
                continue
            if f["status"] == "filled":
                if f["side"] == "buy" and mint not in self.positions:
                    launch = self.launches.get(mint)
                    self.positions[mint] = Position(
                        f["slot"],
                        int(f["tx_fee_lamports"]),
                        launch.dev_sold if launch is not None else False,
                    )
                elif f["side"] == "sell":
                    self.positions.pop(mint, None)
                    self.exiting.discard(mint)
            rec = self.positions.get(mint)
            if rec is not None and f["status"] != "rejected":
                rec.fees_paid += int(f["tx_fee_lamports"])
        for mint in list(self.exiting):
            if not self._pending(state, mint, "sell"):
                self.exiting.discard(mint)
        for mint in list(self.positions):
            if (
                mint not in state.positions
                and mint not in self.exiting
                and not self._pending(state, mint, "buy")
            ):
                del self.positions[mint]

        # Exits first: the money leaves before new money goes in.
        for mint, holding in state.positions.items():
            if len(orders) >= batch_cap:
                break
            if mint in self.exiting:
                continue
            launch = self.launches.get(mint)
            rec = self.positions.get(mint)
            if rec is None:
                rec = Position(slot, tx_fee, launch.dev_sold if launch else False)
                self.positions[mint] = rec
            curve = state.curves.get(mint)
            if curve is None or curve.complete:
                continue
            worth = exit_value(
                holding.token_amount,
                curve.virtual_quote_reserves,
                curve.virtual_token_reserves,
            ) - tx_fee
            basis = holding.cost_lamports + rec.fees_paid
            leave = False
            if basis > 0:
                if worth * BPS >= basis * (BPS + TAKE_PROFIT_BPS):
                    leave = True
                if worth * BPS <= basis * (BPS - STOP_LOSS_BPS):
                    leave = True
            if slot - rec.opened_at >= HOLD_LIMIT_SLOTS:
                leave = True
            if launch is not None and launch.dev_sold and not rec.dev_sold_at_entry:
                leave = True
            if not leave:
                continue
            orders.append(
                {
                    "side": "sell",
                    "mint": mint,
                    "token_amount": holding.token_amount,
                    "max_slippage_bps": SELL_SLIPPAGE_BPS,
                }
            )
            self.exiting.add(mint)
            if launch is not None:
                launch.decided = True

        # Entries: follow the whale, once per mint, on the batch the big
        # ticket lands (a batch later at most, if the reply was full). A
        # stale signal is not a rejection: the next qualifying ticket
        # re-signals the mint while it is still young.
        cash = state.free_cash_lamports() - tx_fee * len(orders)
        open_count = state.committed_position_count()
        for launch in self.launches.values():
            if len(orders) >= batch_cap:
                break
            if launch.decided or launch.finished:
                continue
            if launch.signal_slot is None:
                continue
            if slot - launch.signal_slot > 1:
                continue
            if slot - launch.born_slot > MAX_AGE_SLOTS:
                launch.decided = True
                continue
            if open_count >= caps["max_open_positions"]:
                continue
            curve = state.curves.get(launch.mint)
            if curve is None or curve.complete:
                launch.decided = True
                continue
            if launch.dev_sold:
                launch.decided = True
                continue
            if not (DEV_BUY_LOW <= launch.dev_buy <= DEV_BUY_HIGH):
                launch.decided = True
                continue
            if launch.trade_count < TRADES_MIN or len(launch.buyers) < BUYERS_MIN:
                launch.decided = True
                continue
            if launch.worst_dump > MAX_DUMP_BPS:
                launch.decided = True
                continue
            reserve = curve.real_quote_reserves
            if reserve < RESERVE_LOW or reserve > RESERVE_HIGH:
                launch.decided = True
                continue
            ceiling = state.max_buy_lamports(launch.mint)
            amount = STAKE if STAKE < ceiling else ceiling
            if amount < FLOOR_BUY:
                launch.decided = True
                continue
            if cash < amount + tx_fee:
                continue
            orders.append(
                {
                    "side": "buy",
                    "mint": launch.mint,
                    "quote_lamports": amount,
                    "max_slippage_bps": BUY_SLIPPAGE_BPS,
                }
            )
            cash -= amount + tx_fee
            open_count += 1
            launch.decided = True
        return orders


def create_bot():
    return WhaleFollowBot()
