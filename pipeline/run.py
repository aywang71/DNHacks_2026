"""Orchestrator: python -m pipeline.run --all | --stage <name> [--draws N] [--top N].

A plain ordered list of stage functions with a --stage filter. Each stage reads
and writes files under data/derived/ (config.DERIVED), so any stage can be
rerun alone. Stages that are not implemented yet raise NotImplementedError.
"""

from __future__ import annotations

import argparse
import importlib
import time

from . import config

# (stage name, module, callable, kwargs it accepts) in dependency order.
STAGES = [
    ("reference", "pipeline.reference", "run", ()),          # S0
    ("load", "pipeline.load", "run", ()),                    # S1
    ("enrich", "pipeline.enrich_api", "run", ()),            # S1' (optional; needs 2017-2019 bronze)
    ("pair", "pipeline.pair_t0", "run", ()),                 # S3
    ("feasibility", "pipeline.feasibility", "run", ()),      # S2
    ("context", "pipeline.context", "run", ()),              # S4
    ("null", "pipeline.nulls", "run", ("draws",)),           # S5
    ("features", "pipeline.features", "run", ()),            # S6a
    ("score", "pipeline.score", "run", ()),                  # S6b
    ("corroborate", "pipeline.corroborate", "run", ()),      # S7
    ("export", "pipeline.export", "run", ()),                # S8
    ("narrate", "pipeline.narrate", "run", ("top",)),        # S9
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pipeline.run")
    parser.add_argument("--all", action="store_true", help="run every stage in order (narrate excluded)")
    parser.add_argument("--stage", action="append", default=[], help="stage name; repeatable, run in canonical order")
    parser.add_argument("--draws", type=int, default=config.NULL_DRAWS)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)

    wanted = {name for name, *_ in STAGES if name != "narrate"} if args.all else set(args.stage)
    unknown = wanted - {name for name, *_ in STAGES}
    if unknown:
        parser.error(f"unknown stage(s): {sorted(unknown)}; choose from {[s[0] for s in STAGES]}")
    if not wanted:
        parser.error("nothing to run: pass --all or --stage <name>")

    config.DERIVED.mkdir(parents=True, exist_ok=True)
    for name, module_name, func_name, accepted in STAGES:
        if name not in wanted:
            continue
        kwargs = {k: getattr(args, k) for k in accepted}
        started = time.perf_counter()
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as error:
            if error.name == module_name:
                raise NotImplementedError(f"stage '{name}' ({module_name}) is not implemented yet") from None
            raise
        getattr(module, func_name)(**kwargs)
        print(f"[pipeline] {name}: {time.perf_counter() - started:.1f} s")


if __name__ == "__main__":
    main()
