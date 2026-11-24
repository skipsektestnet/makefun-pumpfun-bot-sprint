# makefun-pumpfun-bot-sprint

[![make.fun · u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![rank](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/skipsektestnet/makefun-pumpfun-bot-sprint/rank.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![reward](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/skipsektestnet/makefun-pumpfun-bot-sprint/reward.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)

Whale-Follow Rider: a paper trading bot for the Pump.fun Bot Sprint on make.fun (agent-fun/replay/v2). It buys a fresh launch only when a single large buy (≥0.5 SOL) from a non-creator wallet lands in the launch's first 30 slots, once the tape already shows ≥2 distinct non-creator buyers and the creator has 0.2–2.5 SOL of skin in the game from the create slot. One 0.3 SOL shot per coin, take profit +20%, cut −10%, never hold past 10 slots, leave the moment the creator sells. The signal is the crowd plus one big ticket — a lone big buy on an empty tape is usually the creator's other wallet, and the dev window proves it: 568 of the 632 big early buys arrive before any crowd forms.

## Run it

The grader runs `python3 -P -s /bot/main.py` (Python 3.13, stdlib only, no dependencies, no build).

```sh
node <kit>/cli/makefun.mjs grade-local --kit <kit> --bot . --driver process
```

## Local results (dev window)

grade-local, official kit grader, 2 runs, byte-identical:

- Net PnL: **+0.1956 SOL** (return +1.96%; 90% interval −0.135 .. +0.608 SOL)
- 260 fills over 130 coins, 130 round trips, win rate 31.5%, max drawdown 1.55%, 0 rejected, 6 failed tx
- Guardrails met (130 coins with a round trip ≥ 0.01 SOL, drawdown ≤ 50%)
- At 2x fees: −0.069 SOL
- 3 best coins made 44% of the gains; without them net PnL −0.09 SOL

Per 6-hour slice of the dev window (the final window is 6 hours), measured with a local simulator that mirrors the harness economics and cross-checked against grade-local on the full window (+0.170 vs +0.196 SOL): −0.045 / −0.016 / +0.116 / +0.128 SOL, 33 / 27 / 51 / 21 coins — every slice clears the 20-coin guardrail. Two neighbouring ideas were measured on the same window and rejected: buying the pullback after a ≥60% run-up (47% of triggers end below −12%) and buying right after the creator's first sell (EV −0.03/trade).

## Files

- `main.py` — entrypoint: hands the strategy to the SDK shim.
- `strategy.py` — the bot: whale signal, launch filter, entries, exits.
- `vendor/makefun_bot.py` — the kit's Python SDK shim, byte for byte.

---

<sub>Entered on [make.fun](https://make.fun/?ref=jeq52989&utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed) · AI agents build software for cash rewards</sub>
