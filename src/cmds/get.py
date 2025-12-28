import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

from ..constants import OUTPUTS_DIR, INPUTS_DIR, ZIP_FILE, DOWNLOADS_DIR
from ..merkle import MerkleForest
from .shared import (
    verbose_print,
    find_collection_metadatas,
    find_identifier_collection,
)


def download_ia_files(identifier):
    """Download all files for an identifier from Internet Archive.

    Returns a list of (filename, filepath) tuples for successfully downloaded files.
    """
    # Create downloads directory structure
    download_dir = os.path.join(DOWNLOADS_DIR, identifier)
    os.makedirs(download_dir, exist_ok=True)

    # Fetch metadata to get file list
    metadata_url = f"https://archive.org/metadata/{identifier}"
    verbose_print(f"Fetching metadata from {metadata_url}")

    try:
        with urllib.request.urlopen(metadata_url, timeout=30) as response:
            metadata = json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error: Could not fetch metadata for '{identifier}': {e}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Network error fetching metadata: {e}")
        sys.exit(1)

    if "files" not in metadata:
        print(f"Error: No files found for identifier '{identifier}'")
        sys.exit(1)

    files = metadata["files"]
    downloaded = []

    print(f"Downloading {len(files)} files to {download_dir}/")
    for i, file_info in enumerate(files, 1):
        filename = file_info["name"]
        file_url = f"https://archive.org/download/{identifier}/{urllib.parse.quote(filename)}"
        filepath = os.path.join(download_dir, filename)

        # Create subdirectories if needed
        file_dir = os.path.dirname(filepath)
        if file_dir:
            os.makedirs(file_dir, exist_ok=True)

        verbose_print(f"  [{i}/{len(files)}] {filename}")

        try:
            urllib.request.urlretrieve(file_url, filepath)
            downloaded.append((filename, filepath))
        except Exception as e:
            print(f"  Warning: Failed to download {filename}: {e}")

    print(f"Downloaded {len(downloaded)}/{len(files)} files")
    return downloaded


def compute_file_hashes(filepath):
    """Compute SHA1, MD5, and CRC32 hashes for a file."""
    import zlib

    sha1 = hashlib.sha1()
    md5 = hashlib.md5()
    crc32 = 0

    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha1.update(chunk)
            md5.update(chunk)
            crc32 = zlib.crc32(chunk, crc32)

    # CRC32 as lowercase hex without 0x prefix, 8 chars
    crc32_hex = format(crc32 & 0xFFFFFFFF, "08x")

    return sha1.hexdigest(), md5.hexdigest(), crc32_hex


def get(args):
    """Download identifier files and show timestamp status."""
    identifier = args.identifier

    # First, get the timestamped hashes from ohara
    zip_path = os.path.join(INPUTS_DIR, "internet_archive", "metadata", ZIP_FILE)

    print(f"Loading archive...")
    timestamped_files = {}
    timestamp_date = None

    with zipfile.ZipFile(zip_path) as z:
        try:
            with z.open(f"{identifier}.txt") as f:
                content = f.read().decode()
                for line in content.splitlines():
                    name, sha1, md5, crc32 = line.split(",")
                    timestamped_files[name] = {
                        "sha1": sha1,
                        "md5": md5 or None,
                        "crc32": crc32 or None,
                    }
        except KeyError:
            print(f"Error: Identifier '{identifier}' not found in timestamped archive.")
            sys.exit(1)

        # Get timestamp date by verifying the collection
        itemlist_filename, itemlist = find_identifier_collection(identifier)
        if itemlist_filename:
            metadatas = find_collection_metadatas(itemlist, z)
            forest = MerkleForest(metadatas)
            root_hash = forest.root.hex()

            ots_path = os.path.join(OUTPUTS_DIR, root_hash + ".digest.ots")
            if os.path.exists(ots_path):
                # Get attestation info from ots verify
                result = subprocess.run(
                    ["ots", "verify", ots_path], capture_output=True, text=True
                )
                for line in result.stderr.strip().split("\n"):
                    if "Bitcoin block" in line:
                        timestamp_date = line.strip()
                        break

    # Download the files
    print()
    downloaded = download_ia_files(identifier)

    # Compare downloaded files with timestamped hashes
    print()
    print("=" * 60)
    print("TIMESTAMP VERIFICATION RESULTS")
    if timestamp_date:
        print(f"Timestamp: {timestamp_date}")
    print("=" * 60)

    matched = []
    mismatched = []
    not_timestamped = []

    for filename, filepath in downloaded:
        if filename not in timestamped_files:
            not_timestamped.append(filename)
            continue

        expected = timestamped_files[filename]
        actual_sha1, actual_md5, actual_crc32 = compute_file_hashes(filepath)

        # Check if hashes match
        sha1_match = actual_sha1 == expected["sha1"]
        md5_match = expected["md5"] is None or actual_md5 == expected["md5"]
        crc32_match = expected["crc32"] is None or actual_crc32 == expected["crc32"]

        if sha1_match and md5_match and crc32_match:
            matched.append(filename)
        else:
            mismatched.append({
                "filename": filename,
                "expected": expected,
                "actual": {"sha1": actual_sha1, "md5": actual_md5, "crc32": actual_crc32}
            })

    # Print results
    if matched:
        print(f"\nTIMESTAMPED FILES ({len(matched)}):")
        for filename in matched:
            print(f"  ✓ {filename}")

    if not_timestamped:
        print(f"\nNOT IN TIMESTAMP ({len(not_timestamped)}):")
        for filename in not_timestamped:
            print(f"  - {filename}")

    if mismatched:
        print(f"\nHASH MISMATCH ({len(mismatched)}):")
        for item in mismatched:
            print(f"  ✗ {item['filename']}")
            print(f"    Expected SHA1: {item['expected']['sha1']}")
            print(f"    Actual SHA1:   {item['actual']['sha1']}")

    # Summary
    print()
    print(f"Summary: {len(matched)} timestamped, {len(not_timestamped)} not in timestamp, {len(mismatched)} mismatched")
