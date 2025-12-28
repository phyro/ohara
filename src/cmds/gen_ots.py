import io
import os
import sys
import zipfile

from ..constants import OUTPUTS_DIR, INPUTS_DIR, ZIP_FILE
from ..merkle import MerkleForest
from ..ots import create_ots_from_proof
from .shared import (
    verbose_print,
    find_collection_metadatas,
    find_identifier_collection,
)


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
