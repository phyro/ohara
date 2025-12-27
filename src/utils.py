import os


def read_file(file_path, mode="rb"):
    with open(file_path, mode) as f:
        return f.read()


def find_files(directory, ext):
    """Find all .<ext> files in the given directory (non-recursively)."""

    return [
        my_file
        for my_file in os.listdir(directory)
        if my_file.lower().endswith(ext)
        and os.path.isfile(os.path.join(directory, my_file))
    ]
