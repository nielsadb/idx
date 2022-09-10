
import re
import typer
import pickle
import pretty_errors
import stat

from pathlib import Path
from dixpy import Node, scan
from dataclasses import dataclass
from typing import TypeVar, Type
from collections import defaultdict

app = typer.Typer()


@dataclass
class Config:
    root: Path
    top: Node
    verbose: bool


def make_singleton(t: Type):
    _cfg: list[t] = [None]

    def set(cfg: t):
        _cfg[0] = cfg

    def get() -> t:
        return _cfg[0]
    return set, get


set_sfg, get_cfg = make_singleton(Config)


def out_msg(str: str, verbose: bool = None):
    if verbose == None:
        verbose = get_cfg().verbose
    if verbose:
        print(f"# str")


def fatal(str: str):
    out_msg(str, True)
    exit(1)


@app.callback()
def load(root: Path, verbose: bool = False):
    try:
        with open("clean_cache.pickle", "rb") as fd:
            top = pickle.load(fd)
    except FileNotFoundError:
        top = scan(root, True)
        with open("clean_cache.pickle", "wb") as fd:
            pickle.dump(top, fd)
    set_sfg(Config(root, top, verbose))


@app.command()
def rmjunk(tag: str):
    junk_patterns = [r'\.jpg$', r'\.jpeg$', r'\.exe$', r'\.txt$', r'\.nfo$',
                     r'\.url$', r'^\.DS_Store$', r'^Samples$', r'^Covers$', r'^Subs$']
    junk_regexps = [re.compile(pattern) for pattern in junk_patterns]

    def is_junk(node: Node):
        name = node.path.name
        return any(pattern.search(name) for pattern in junk_regexps)

    def is_tagged(node: Node):
        return tag.lower() in set(tag.lower() for tag in node.tags)

    for node in get_cfg().top.children.values():
        if stat.S_ISDIR(node.stat.st_mode) and is_tagged(node):
            keep = []
            for child in node.children.values():
                if is_junk(child):
                    print(f'rm -r "{child.path.as_posix()}"')
                else:
                    keep.append(child)
            if len(keep) == 1:
                child = keep[0].path
                ugly = re.match(r'^(.*)\[[^\]]*\]$', node.path.name)
                clean = ugly[1] if ugly else node.path.name
                if child.name.lower().startswith(clean.lower()):
                    new_name = child.name
                else:
                    extension = re.match(r'^.*(\.[^\.]*)$', child.name)
                    new_name = clean + (extension[1] if extension else '')
                new_path = node.path.parent/new_name
                print(f'mv "{child.as_posix()}" "{new_path.as_posix()}"')
                for tag in node.tags:
                    print(f'tag -a {tag} "{new_path.as_posix()}"')
                print(f'rmdir "{node.path.as_posix()}"')


@app.command()
def mv(tag: str):
    folder = get_cfg().root/tag
    print(f'mkdir -p "{folder.as_posix()}"')
    for node in get_cfg().top.children.values():
        if tag in node.tags:
            print(f'mv "{node.path.as_posix()}" "{folder.as_posix()}"')


if __name__ == "__main__":
    app()
