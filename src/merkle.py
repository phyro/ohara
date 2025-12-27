# Don't trust me with cryptography.

from functools import reduce
import hashlib
import math


def H(el):
    """Computes the sha256 hash of an element."""
    return hashlib.sha256(el).digest()


# NOTE: This check is a mathematical proof independent of the structure itself.
def verify_inclusion_proof(root_hash_hex, hash_seq):
    """Verify an inclusion proof sequence."""

    def hashup(el, pair):
        assert pair[0] in {"append", "prepend"}
        left, right = (el, pair[1]) if pair[0] == "append" else (pair[1], el)
        return H(left + right)

    computed_root_hash = reduce(hashup, hash_seq[1:], hash_seq[0])
    return computed_root_hash.hex() == root_hash_hex


class MerkleTree:
    """A simple Merkle tree with 2^n elements."""

    def __init__(self, elements):
        rv = math.log(len(elements), 2)
        assert rv == int(rv)  # must be 2^n
        self.tree = self.build_tree(elements)

    def build_tree(self, elements):
        hashed_leaves = list(map(lambda x: H(x.encode()), elements))
        # Add elements as the lowest level
        return self._build_tree(hashed_leaves) + [elements]

    def _build_tree(self, elements):
        if len(elements) == 0:
            raise Exception("No elements given.")
        if len(elements) == 1:
            return [elements]

        # When we reach here we'll always have 2^n number of elements which is divisible by 2
        next_level = [
            H(elements[i] + elements[i + 1]) for i in range(0, len(elements), 2)
        ]
        # Result is the next level followed by the one below it
        return self._build_tree(next_level) + [elements]

    def prove_inclusion(self, el_pos, level):
        if level == 0:
            return []

        cur = (
            ("append", self.tree[level][el_pos + 1])
            if el_pos % 2 == 0
            else ("prepend", self.tree[level][el_pos - 1])
        )

        return [cur] + self.prove_inclusion(el_pos // 2, level - 1)

    def verify_inclusion(self, hash_seq):
        return verify_inclusion_proof(self.root.hex(), hash_seq)

    @property
    def root(self):
        return self.tree[0][0]

    @property
    def elements(self):
        return self.tree[-1]


class MerkleForest:
    """A simple append-only Merkle tree implementation with a perfect forest (MMR style).


    [          H17           ]
    [    H13         H16     ]
    [ H11   H12   H14   H15  ] [ H18 ]
    [H0 H1 H2 H3 H4 H5 H6 H7 ] [H8 H9] [H10]
    [0, 1, 2, 3, 4, 5, 6, 7  ] [8,  9] [10 ]

    """

    def __init__(self, elements):
        self.trees = self._build(elements)

    def _build(self, elements):
        """Partition the elements in merkle trees."""
        partitions = self._partition_leaves(elements)
        return [MerkleTree(partition_elements) for partition_elements in partitions]

    @property
    def elements(self):
        return sum([tree.elements for tree in self.trees], [])

    @property
    def root(self):
        root_hashes = [tree.root for tree in self.trees]
        # We build the tree root for right to left.
        # NOTE: The reason we swap the x+acc is because we reversed the root hashes
        # [1, 2, 3]
        # [3, 2, 1]
        return reduce(lambda acc, x: H(x + acc), root_hashes[::-1])

    def _find_tree(self, el):
        """Find the tree which contains the given element."""
        for tree_idx, tree in enumerate(self.trees):
            try:
                pos = tree.elements.index(el)
                return tree_idx, pos
            except:  # not found in this tree
                continue

        raise Exception(f"Element {el} not found in any tree.")

    def prove_inclusion(self, el):
        """Construct an inlusion proof for an element at a certain (index) position."""
        tree_idx, pos = self._find_tree(el)

        # Get inclusion to that merkle tree root
        mt = self.trees[tree_idx]
        mt_proof = [mt.tree[len(mt.tree) - 2][pos]] + mt.prove_inclusion(
            pos, len(mt.tree) - 2  # -2 because we skip the 'elements' level
        )

        # The prepend/append position is equal to their position
        roots = [tree.root for tree in self.trees]
        left_roots = roots[:tree_idx]
        right_roots = roots[tree_idx + 1 :]

        append = []  # This will have either 0 or 1 element (rollup from right)
        if right_roots:
            # Reduce right-to-left to match forest.root computation order
            append = [("append", reduce(lambda acc, x: H(x + acc), right_roots[::-1]))]

        # Left roots must be prepended in reverse order to match forest.root computation
        proof = (
            mt_proof
            + append
            + [("prepend", left_root) for left_root in reversed(left_roots)]
        )
        return proof

    def verify_inclusion(self, hash_seq):
        return verify_inclusion_proof(self.root.hex(), hash_seq)

    def _partition_leaves(self, elements):

        def get_partitions(num):
            rv = []
            for n in range(50, -1, -1):
                cur_exp = 2**n
                if num >= cur_exp:
                    rv.append(cur_exp)
                    num -= cur_exp
            return rv

        partitions = get_partitions(len(elements))

        pos = 0
        trees = []
        for partition_len in partitions:
            trees.append(elements[pos : pos + partition_len])
            pos += partition_len

        return trees
