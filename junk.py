import re
from dixpy import Node

JUNK_PATTERNS = [
    r"\.jpg$",
    r"\.jpeg$",
    r"\.exe$",
    r"\.txt$",
    r"\.nfo$",
    r"\.url$",
    r"^\.DS_Store$",
    r"^Samples$",
    r"^Covers$",
    r"^Subs$",
]
JUNK_REGEXPS = [re.compile(pattern) for pattern in JUNK_PATTERNS]

def is_junk(node: Node):
    name = node.path.name
    return any(pattern.search(name) for pattern in JUNK_REGEXPS)
