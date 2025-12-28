import os
import sys
import zipfile

from ..constants import INPUTS_DIR, ZIP_FILE
from .shared import find_identifier_collection, verify_collection


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
