# from __future__ import annotations

from os import stat_result
from pathlib import Path
from typing import Dict, Set, NamedTuple, Optional, Any, List
import json
import subprocess
import pickle
from xmlrpc.client import Boolean

TAGPROG = 'tag'  # https://github.com/jdberry/tag

def _exhaust(generator):
    for x in generator:
        pass

class Node(NamedTuple):
    path: Path
    stat: Optional[stat_result]
    tags: Set[str]
    children: Dict[str, 'Node']

    def walk(self, downf, init = None, upf = _exhaust):
        def visit(node:Node, down):
            down = downf(node, down)
            up = upf(visit(child, down) for child in node.children.values())
            return up
        return visit(self, init)


def make_node(path: Path, tags: Set[str], do_stat: bool):
    stat = path.stat() if do_stat else None
    return Node(path=path, tags=tags, stat=stat, children={})


FlatNodes = Dict[Path, Node]


def read_tags(root: Path, do_stat: bool) -> FlatNodes:
    tagprog = subprocess.run(
        [TAGPROG, '-R', '-l', root.as_posix()], stdout=subprocess.PIPE)
    output = tagprog.stdout.decode('utf-8')

    def make_pair(line):
        parts = line.split('\t') + ['']
        path = root/(parts[0].strip())
        tags = set(x for x in parts[1].split(',') if len(x) > 0)
        return path, make_node(path, tags, do_stat)
    return dict(make_pair(line) for line in output.splitlines())


def find_nested(path: Path, top: Node):
    # TODO: sanity check that path is a decendant of top
    entry = top
    for name in path.parts[len(top.path.parts):]:
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

def scan(root: Path, do_stat: Boolean = False):
    return make_nested(read_tags(root, do_stat), root)

def print_tree(node: Node, infof):
    def rec(node: Node, parent: Node, level: int):
        is_dir = len(node.children) > 0
        print(
            f'{"  " * level}{infof(node, parent)} {node.path.name}{" {" if is_dir else ""}')
        for child in sorted(node.children.keys()):
            rec(node.children[child], node, level+1)
        if is_dir:
            print(f'{"  " * level}}}')
    rec(node, None, 0)
