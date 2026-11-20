"""Walkable tunnels on the submarine specimen, in native Vim buffer coordinates."""
from collections import deque
from itertools import pairwise

MOVES = {"h": (0, -1), "j": (1, 0), "k": (-1, 0), "l": (0, 1)}
# First line is the main passage; the others are branches.
TUNNELS = (
    (((3, 20), (6, 20)), ((4, 20), (4, 13), (7, 13)), ((3, 20), (3, 26))),
    (((6, 20), (6, 26), (2, 26)), ((6, 20), (9, 20), (9, 15)),
     ((6, 23), (3, 23), (3, 16))),
    (((2, 26), (8, 26), (8, 15), (5, 15)), ((5, 26), (5, 21), (3, 21)),
     ((8, 20), (11, 20), (11, 27)), ((2, 26), (2, 29))),
)


def map_rows(stage):
    passages = set()
    for route in TUNNELS[stage]:
        for (y, x), (ey, ex) in pairwise(route):
            dy, dx = (ey > y) - (ey < y), (ex > x) - (ex < x)
            passages.add((y, x))
            while (y, x) != (ey, ex):
                y, x = y+dy, x+dx
                passages.add((y, x))
    grid = [[" "] * 40 for _ in range(16)]
    for y, x in passages:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (y+dy, x+dx) not in passages:
                    grid[y+dy][x+dx] = "#"
        grid[y][x] = "."
    end = TUNNELS[stage][0][-1]
    grid[end[0]][end[1]] = "*"
    return ["".join(row) for row in grid]


def walk(rows, pos, key, count):
    travelled = []
    dy, dx = MOVES[key]
    for _ in range(count):
        y, x = pos[0]+dy, pos[1]+dx
        if not (0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] in ".*"):
            break
        pos = y, x
        travelled.append(pos)
        if rows[y][x] == "*":
            break
    return travelled


def hint(rows, start, end):
    queue = deque([(start, "")])
    seen = {start}
    while queue:
        pos, path = queue.popleft()
        if pos == end and path:
            count = len(path) - len(path.lstrip(path[0]))
            return (str(count) if count > 1 else "") + path[0]
        for key in MOVES:
            for dest in walk(rows, pos, key, 1):
                if dest not in seen:
                    seen.add(dest)
                    queue.append((dest, path+key))
    return ""
