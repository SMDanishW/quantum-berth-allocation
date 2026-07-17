"""BACAP command-line interface (Phase 1: `generate`; Phase 3 adds `solve`)."""

from __future__ import annotations

import argparse
from pathlib import Path

from bacap.instances.generator import generate_instance
from bacap.instances.schema import save_instance


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="bacap.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate a synthetic instance")
    gen.add_argument("--n", type=int, required=True, help="number of vessels")
    gen.add_argument("--congestion", type=float, required=True, help="target rho in (0,1)")
    gen.add_argument("--seed", type=int, required=True)
    gen.add_argument("--out", type=Path, required=True, help="output directory")

    args = parser.parse_args(argv)

    inst = generate_instance(args.n, args.congestion, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{inst.instance_id}.json"
    save_instance(inst, path)
    print(path)


if __name__ == "__main__":
    main()
