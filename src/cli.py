import argparse
import sys

from .cmds import shared
from .cmds.verify import verify
from .cmds.read import read
from .cmds.gen_ots import generate_ots
from .cmds.get import get


def build_args_parser():
    parser = argparse.ArgumentParser(
        description="A program that verifies internet archive collections."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output."
    )
    subparsers = parser.add_subparsers(
        title="Commands", description="The main command is 'verify'."
    )
    # verify command
    parser_verify = subparsers.add_parser(
        "verify", aliases=["v"], help="Verifies timestamps of collections."
    )
    parser_verify.set_defaults(func=verify)

    # read command
    parser_read = subparsers.add_parser(
        "read",
        aliases=["r"],
        help="Shows the committed hashes for the given identifier.",
    )
    parser_read.add_argument(
        "identifier", type=str, help="Internet Archive's identifier."
    )
    parser_read.add_argument(
        "--verify", action="store_true", help="Verify the identifier."
    )
    parser_read.set_defaults(func=read)

    # gen-ots command
    parser_genots = subparsers.add_parser(
        "gen-ots",
        aliases=["go"],
        help="Generates OTS proofs for the given identifiers.",
    )
    parser_genots.add_argument(
        "identifiers", type=str, nargs="+", help="Internet Archive identifier(s)."
    )
    parser_genots.set_defaults(func=generate_ots)

    # get command
    parser_get = subparsers.add_parser(
        "get",
        aliases=["g"],
        help="Downloads identifier files from Internet Archive and shows their timestamp status.",
    )
    parser_get.add_argument(
        "identifier", type=str, help="Internet Archive's identifier."
    )
    parser_get.set_defaults(func=get)

    return parser


def main():
    parser = build_args_parser()
    args = parser.parse_args(sys.argv[1:])

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    shared.set_verbose(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
