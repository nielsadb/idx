
import re
import sys
import typer
import pickle
import pretty_errors
import urllib.parse

from pathlib import Path
from dixpy import Node, scan
from dataclasses import dataclass
from rich import print

### Cached indices ###################################

app = typer.Typer()

@dataclass
class Config:
    top: Node

def _make_singleton():
    _cfg: list[Config] = [None]
    def set_cfg(cfg:Config):
        _cfg[0] = cfg
    def get_cfg() -> Config:
        return _cfg[0]
    return set_cfg, get_cfg
set_sfg, get_cfg = _make_singleton()    

def out_msg(str:str):
    pass

def fatal(str:str):
    print(str)
    exit(1)

DEFAULT_CACHE_FILE = "idx_cache.pickle"
@app.callback()
def load(dir:str, cache:str = DEFAULT_CACHE_FILE):
    cache_file = Path(cache)
    root = Path(dir).resolve()
    def get_top():
        if cache_file.exists():
            out_msg(f"loading cache from {cache_file}.")
            with open(cache_file, "rb") as fd:
                cache = pickle.load(fd)
        else:
            cache = {}
        if root in cache:
            out_msg(f"found {root} in cache.")
        else:
            out_msg(f"starting scan of {root}.")
            top = scan(root)
            cache[root] = top
            out_msg(f"storing cache in {cache_file}.")
            with open(cache_file, "wb") as fd:
                pickle.dump(cache, fd)
        return cache[root]
    if root.exists():
        set_sfg(Config(get_top()))
    else:
        fatal(f"{root} does not exist")



### Commands ###################################

@app.command()
def show():
    def visit(node:Node, indent:int):
        tags = ", ".join(node.tags)
        print(f"{indent*'  '}{node.path.name} {f'[{tags}]' if tags else ''}")
        return indent+1
    get_cfg().top.walk(visit, 0)

@app.command()
def search(regexps:list[str], md:int = 1, ic:bool = True):
    crs = [re.compile(r, re.IGNORECASE if ic else 0) for r in regexps]
    root = get_cfg().top.path
    result_count = [0]
    def visit(node:Node, depth):
        if not node.children and depth >= md:
            term = "/".join(node.path.relative_to(root).parts[md:])
            matches = list(r.search(term) for r in crs)
            if all(matches):
                result_count[0] += 1
                link = f"file://{urllib.parse.quote(node.path.as_posix())}"
                print(f"[bold]*[/bold] [link={link}]{term}[/link]")
        return depth+1
    print(f"[dim]{'-'*80}[/dim]")
    get_cfg().top.walk(visit, 0)
    print(f"[dim]{result_count[0]} results[/dim]")

if __name__ == "__main__":
    app()