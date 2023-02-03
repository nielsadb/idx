from os import stat_result
from pathlib import Path
from typing import (
    Dict,
    Set,
    NamedTuple,
    Optional,
    Any,
    List,
    Callable,
    Generator,
    Tuple,
)
import json
import subprocess
import pickle
from xmlrpc.client import Boolean

TAGPROG = "tag"  # https://github.com/jdberry/tag


def _exhaust(generator):
    for x in generator:
        pass


class Node(NamedTuple):
    path: Path
    stat: Optional[stat_result]
    tags: Set[str]
    children: Dict[str, "Node"]

    def walk(self, downf, init=None, upf=_exhaust):
        def visit(node: Node, down):
            down = downf(node, down)
            up = upf(visit(child, down) for child in node.children.values())
            return up

        return visit(self, init)

    @staticmethod
    def make(path: Path, tags: Set[str]):
        return Node(path=path, stat=path.stat(), tags=tags, children={})


FlatNodes = Dict[Path, Node]


FilterFunc = Callable[[Node], bool]


def read_tags(
    root: Path, filter: Optional[FilterFunc] = None
) -> Generator[Node, None, None]:
    tagparams = ["-e"] if filter else ["-R"]
    proc = [TAGPROG] + tagparams + [root.as_posix()]
    tagprog = subprocess.run(proc, stdout=subprocess.PIPE)
    output = tagprog.stdout.decode("utf-8")

    for line in output.splitlines():
        parts = line.split("\t") + [""]
        node = Node.make(
            path=root / (parts[0].strip()),
            tags=set(x for x in parts[1].split(",") if len(x) > 0),
        )
        if filter:
            if filter(node):
                yield node
                yield from read_tags(root / node.path, None)
            elif node.path == root:
                yield node
        else:
            yield node


def find_nested(path: Path, top: Node):
    # TODO: sanity check that path is a decendant of top
    entry = top
    for name in path.parts[len(top.path.parts) :]:
        entry = entry.children[name]
    return entry


def make_nested(flat: FlatNodes, root: Path):
    for p in sorted(flat.keys(), key=Path.as_posix):
        if p == root:
            top = flat[p]
        else:
            parent = find_nested(p.parent, top)
            parent.children[p.name] = flat[p]
    return top


def scan(root: Path, filter: Optional[FilterFunc] = None):
    flat = dict((node.path, node) for node in read_tags(root, filter))
    return make_nested(flat, root)


def print_tree(node: Node, infof):
    def rec(node: Node, parent: Node, level: int):
        is_dir = len(node.children) > 0
        print(
            f'{"  " * level}{infof(node, parent)} {node.path.name}{" {" if is_dir else ""}'
        )
        for child in sorted(node.children.keys()):
            rec(node.children[child], node, level + 1)
        if is_dir:
            print(f'{"  " * level}}}')

    rec(node, None, 0)
