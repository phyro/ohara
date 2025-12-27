# Ohara - A collection of video timestamps

# List available recipes
default:
    @just --list

# Show timestamped hashes for an identifier
read identifier:
    ohara read {{identifier}}

# Show and verify timestamp against Bitcoin blockchain
read-verify identifier:
    ohara read {{identifier}} --verify

# Verify all collection timestamps
verify:
    ohara verify

# Verify all collections with verbose output
verify-verbose:
    ohara -v verify

# Generate OTS proofs for identifier(s)
gen-ots +identifiers:
    ohara gen-ots {{identifiers}}

# Install package
install:
    pip install .