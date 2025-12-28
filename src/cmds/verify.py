import os
import zipfile

from ..constants import INPUTS_DIR, ZIP_FILE
from ..utils import find_files
from .shared import read_itemlist, verify_collection


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
