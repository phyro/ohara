import io
import os
import subprocess
import sys
import time

from ..constants import OUTPUTS_DIR, INPUTS_DIR
from ..merkle import MerkleForest
from ..utils import find_files, read_file

# Global verbose flag
VERBOSE = False


def set_verbose(value):
    global VERBOSE
    VERBOSE = value


def verbose_print(*args, **kwargs):
    """Print only if verbose mode is enabled."""
    if VERBOSE:
        print(*args, **kwargs)


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
