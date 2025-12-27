import argparse
import io
import os
import sys
import time
import subprocess
import zipfile

from .constants import OUTPUTS_DIR, INPUTS_DIR, ZIP_FILE
from .merkle import MerkleForest
from .utils import find_files, read_file
from .ots import create_ots_from_proof

# Global verbose flag
VERBOSE = False


def verbose_print(*args, **kwargs):
    """Print only if verbose mode is enabled."""
    if VERBOSE:
        print(*args, **kwargs)


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

    return parser


def verify_collection(itemlist, z):
    """Verifies the collection by finding the identifiers metadata, building the merkle tree and comparing the root
    with an ots timestamped root.
    """

    # Get collection metadatas
    metadatas = find_collection_metadatas(itemlist, z)
    # Build merkle tree
    start_time = time.time()
    tree = MerkleForest(metadatas)
    end_time = time.time()
    verbose_print(f"  Merkle forest built in {end_time - start_time:.2f}s")

    root_hash = tree.root.hex()
    verbose_print(f"  Root: {root_hash}")

    # Assert that the root is the same
    content = read_file(os.path.join(OUTPUTS_DIR, root_hash + ".digest"))
    # Assert that the computed root hash is the same as the file content (content is in bytes)
    assert content.hex() == root_hash
    assert content == tree.root
    # TODO: remove later
    content_old = read_file(os.path.join(OUTPUTS_DIR, root_hash + ".hash"))
    assert content_old.decode() == content.hex()

    # Verify the .ots for this tree root
    # root_file_path = os.path.join(OUTPUTS_DIR, root_hash + ".hash.ots")
    root_file_path = os.path.join(OUTPUTS_DIR, root_hash + ".digest.ots")
    result = subprocess.run(
        ["ots", "verify", root_file_path], capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        print("  Check if your Bitcoin node is running with RPC enabled.")
        sys.exit(1)

    assert "Success!" in result.stderr  # success writes land in stderr
    # Extract the attestation date from ots output
    for line in result.stderr.strip().split("\n"):
        if "Bitcoin block" in line or "Success!" in line:
            print(f"  {line.strip()}")


def find_collection_metadatas(itemlist, z):
    """Returns the collection metadata files."""

    result = []
    cnt = 0
    start = time.time()
    for identifier in itemlist:
        # NOTE TextIOWrapper to avoid ^M translation shenanigans
        with io.TextIOWrapper(
            z.open(f"{identifier}.txt"), encoding="utf-8", newline=None
        ) as f:
            metadata = f.read()
            if metadata == "":
                cnt += 1

            result.append(metadata)

    end = time.time()
    verbose_print(f"  Loaded {len(itemlist)} items in {end-start:.2f}s (empty: {cnt})")

    return result


def read_itemlist(itemlist_filename):
    """Returns the itemlist entries in the given file."""

    collections_dir = os.path.join(INPUTS_DIR, "internet_archive", "collections")
    itemlist_path = os.path.join(collections_dir, itemlist_filename)
    itemlist = read_file(itemlist_path, mode="r").split(
        "\n"
    )  # we read with mode="r" because .itemlist files are text not bytes

    # Assert that the last entry is empty and there's only one such entry
    assert (
        len([x for x in itemlist if x == ""]) == 1
    )  # one empty element for newline at the end
    itemlist = [x for x in itemlist if x != ""]  # filter out empty lines

    assert len(itemlist) > 0  # assert we have at least one entry
    return itemlist


def verify(args):
    """Verify all the collections."""

    collection_itemlists = find_files(
        os.path.join(INPUTS_DIR, "internet_archive", "collections"), ".itemlist"
    )

    # Open the zip file once and keep it around because it's a slow process
    zip_path = os.path.join(INPUTS_DIR, "internet_archive", "metadata", ZIP_FILE)
    print(f"Loading archive...")
    with zipfile.ZipFile(zip_path) as z:
        for itemlist_filename in collection_itemlists:
            itemlist = read_itemlist(itemlist_filename)
            print(f"Verifying {itemlist_filename} ({len(itemlist)} items)")

            verify_collection(itemlist, z)


def verify_identifier(identifier, z):
    itemlist_filename, itemlist = find_identifier_collection(identifier)
    if itemlist_filename is None:
        raise Exception("Identifier not found in any timestamped collection.")

    print(f"\nVerifying {itemlist_filename} ({len(itemlist)} items)")
    verify_collection(itemlist, z)


def read(args):

    def pretty_txt(content):
        """Returns a pretty variant of the .txt file content."""
        result = []
        for entry in content.splitlines():
            name, sha1, md5, crc32 = entry.split(",")
            result.append(
                f"Filename: {name}\nSHA1:     {sha1}\nMD5:      {md5 or '-'}\nCRC32:    {crc32 or '-'}"
            )
        return "\n\n".join(result)

    identifier = args.identifier
    zip_path = os.path.join(INPUTS_DIR, "internet_archive", "metadata", ZIP_FILE)
    print(f"Loading archive...")
    with zipfile.ZipFile(zip_path) as z:
        try:
            with z.open(f"{identifier}.txt") as f:
                content = f.read().decode()
                print(pretty_txt(content))
        except KeyError:
            print(f"Error: Identifier '{identifier}' not found.")
            sys.exit(1)
        # Verify identifier if needed
        if args.verify:
            verify_identifier(identifier, z)


def find_identifier_collection(identifier):
    """Find which collection contains the identifier and return (itemlist_filename, itemlist)."""
    collection_itemlists = find_files(
        os.path.join(INPUTS_DIR, "internet_archive", "collections"), ".itemlist"
    )

    for itemlist_filename in collection_itemlists:
        itemlist = read_itemlist(itemlist_filename)
        if identifier in itemlist:
            return itemlist_filename, itemlist

    return None, None


def generate_ots(args):
    """Generates OTS proofs for the given identifiers."""
    identifiers = args.identifiers
    zip_path = os.path.join(INPUTS_DIR, "internet_archive", "metadata", ZIP_FILE)

    # Group identifiers by collection
    collection_to_identifiers = {}
    not_found = []
    for identifier in identifiers:
        itemlist_filename, itemlist = find_identifier_collection(identifier)
        if itemlist_filename is None:
            not_found.append(identifier)
        else:
            if itemlist_filename not in collection_to_identifiers:
                collection_to_identifiers[itemlist_filename] = (itemlist, [])
            collection_to_identifiers[itemlist_filename][1].append(identifier)

    if not_found:
        print(f"Error: Identifier(s) not found: {', '.join(not_found)}")
        sys.exit(1)

    print(f"Loading archive...")
    with zipfile.ZipFile(zip_path) as z:
        for itemlist_filename, (itemlist, ids) in collection_to_identifiers.items():
            print(f"Processing {itemlist_filename} ({len(ids)} identifier(s))")

            # Build the Merkle forest once per collection
            verbose_print(f"  Building Merkle forest ({len(itemlist)} items)...")
            metadatas = find_collection_metadatas(itemlist, z)
            forest = MerkleForest(metadatas)
            forest_root = forest.root.hex()
            verbose_print(f"  Root: {forest_root}")

            # Check OTS file exists
            ots_filename = f"{forest_root}.digest.ots"
            ots_path = os.path.join(OUTPUTS_DIR, ots_filename)
            if not os.path.exists(ots_path):
                print(f"  Warning: OTS file not found at {ots_path}")

            # Export each identifier in this collection
            for identifier in ids:
                try:
                    with io.TextIOWrapper(
                        z.open(f"{identifier}.txt"), encoding="utf-8", newline=None
                    ) as f:
                        metadata = f.read()
                except KeyError:
                    print(f"Error: Identifier '{identifier}' not found.")
                    sys.exit(1)

                # Generate inclusion proof
                proof = forest.prove_inclusion(metadata)

                # Verify the proof locally before exporting
                if not forest.verify_inclusion(proof):
                    print(f"Error: Proof for '{identifier}' failed verification.")
                    sys.exit(1)

                # Write the metadata file
                metadata_filename = f"{identifier}.txt"
                with open(metadata_filename, "w", encoding="utf-8") as f:
                    f.write(metadata)

                # Generate OTS file containing the Merkle proof
                ots_output_filename = f"{identifier}.txt.ots"
                ots_bytes = create_ots_from_proof(metadata, proof, forest_root)
                with open(ots_output_filename, "wb") as f:
                    f.write(ots_bytes)

                print(f"  {metadata_filename}, {ots_output_filename}")

    print(f"\nTo verify: ots verify <identifier>.txt.ots")


def main():
    global VERBOSE
    parser = build_args_parser()
    args = parser.parse_args(sys.argv[1:])

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    VERBOSE = args.verbose
    args.func(args)


if __name__ == "__main__":
    main()
