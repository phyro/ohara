"""OpenTimestamps proof creation and serialization utilities."""

import os

from opentimestamps.core.timestamp import Timestamp, DetachedTimestampFile
from opentimestamps.core.op import OpAppend, OpPrepend, OpSHA256
from opentimestamps.core.serialize import (
    BytesSerializationContext,
    BytesDeserializationContext,
)

from .constants import OUTPUTS_DIR
from .merkle import H


def create_ots_from_proof(metadata, proof, forest_root_hex):
    """Create an OTS file containing the Merkle inclusion proof merged with Bitcoin attestations.

    The generated OTS file chains from SHA256(metadata) through the Merkle proof
    to the forest root, then continues with the existing Bitcoin attestations
    from the .digest.ots file.

    Args:
        metadata: The raw metadata string
        proof: The inclusion proof from MerkleForest.prove_inclusion()
        forest_root_hex: The forest root as a hex string

    Returns:
        bytes: The serialized OTS file content
    """
    # Load the existing .digest.ots file for this forest root
    digest_ots_path = os.path.join(OUTPUTS_DIR, f"{forest_root_hex}.digest.ots")
    if not os.path.exists(digest_ots_path):
        raise FileNotFoundError(f"OTS file not found: {digest_ots_path}")

    with open(digest_ots_path, "rb") as f:
        existing_ots_bytes = f.read()

    # Deserialize the existing OTS file
    ctx = BytesDeserializationContext(existing_ots_bytes)
    existing_dtf = DetachedTimestampFile.deserialize(ctx)

    # Start with the metadata hash
    metadata_hash = H(metadata.encode())
    timestamp = Timestamp(metadata_hash)

    # Build the chain: for each step, append/prepend the sibling, then SHA256
    current = timestamp
    for item in proof[1:]:  # Skip the first element (leaf hash)
        op_type, sibling = item

        if op_type == "append":
            current = current.ops.add(OpAppend(sibling))
        else:  # prepend
            current = current.ops.add(OpPrepend(sibling))

        # Apply SHA256 after each operation
        current = current.ops.add(OpSHA256())

    # Verify our chain produces the correct forest root
    forest_root_bytes = bytes.fromhex(forest_root_hex)
    assert (
        current.msg == forest_root_bytes
    ), f"Chain mismatch: {current.msg.hex()} != {forest_root_hex}"

    # The .digest.ots file starts with SHA256(forest_root) due to file_hash_op
    # We need to add one more SHA256 to match
    current = current.ops.add(OpSHA256())

    # Now current.msg should match existing_dtf.timestamp.msg
    assert (
        current.msg == existing_dtf.timestamp.msg
    ), f"After SHA256 mismatch: {current.msg.hex()} != {existing_dtf.timestamp.msg.hex()}"

    # Merge the existing timestamp's operations and attestations into our chain
    current.merge(existing_dtf.timestamp)

    # Create the final file with SHA256 as the file hash operation
    final_dtf = DetachedTimestampFile(OpSHA256(), timestamp)

    # Serialize to bytes
    out_ctx = BytesSerializationContext()
    final_dtf.serialize(out_ctx)
    return out_ctx.getbytes()
