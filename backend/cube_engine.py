"""Kociemba URFDLB facelets. Clockwise is viewed from outside the turned face.

Each sticker has a position and an outward normal. A turn rotates both; matching
the resulting geometry generates a destination-to-source permutation once.
"""
from collections import Counter
from typing import Iterable

FACES = 'URFDLB'
MOVES = tuple(f + suffix for f in 'UDLRFB' for suffix in ('', "'", '2'))
LEGEND = (
    '54 facelets: U[0:9] R[9:18] F[18:27] D[27:36] L[36:45] B[45:54]. '
    'Each face is row-major as viewed from outside, indices 0 1 2 / 3 4 5 / 6 7 8; '
    'center index 4. Net: U above F; L F R B across; D below F. '
    'U top, R right, F front, D bottom, L left, B back. '
    'Solved: each face uniform with its center letter. Clockwise viewed from outside.'
)
NAMES = dict(zip(FACES, ('upper', 'right', 'front', 'lower', 'left', 'back')))
DEFINITIONS = {
    m: f'Turn the {NAMES[m[0]]} face ' + (
        'by 180 degrees' if m.endswith('2') else
        'counterclockwise by 90 degrees' if m.endswith("'") else 'clockwise by 90 degrees'
    ) for m in MOVES
}


def solved_state() -> str:
    return ''.join(f * 9 for f in FACES)


def deserialize(value: str) -> str:
    if not isinstance(value, str) or len(value) != 54 or Counter(value) != Counter(solved_state()):
        raise ValueError('Expected 54 URFDLB letters, nine of each')
    if any(value[i * 9 + 4] != f for i, f in enumerate(FACES)):
        raise ValueError('Centers must use fixed URFDLB orientation')
    return value  # color/center validation; physical reachability is guaranteed for generated puzzles


def serialize(state: str) -> str:
    return deserialize(state)


def _geometry():
    out = []
    for f in FACES:
        for r in range(3):
            for c in range(3):
                p, n = {
                    'U': ((c-1, 1, r-1), (0, 1, 0)),
                    'R': ((1, 1-r, 1-c), (1, 0, 0)),
                    'F': ((c-1, 1-r, 1), (0, 0, 1)),
                    'D': ((c-1, -1, 1-r), (0, -1, 0)),
                    'L': ((-1, 1-r, c-1), (-1, 0, 0)),
                    'B': ((1-c, 1-r, -1), (0, 0, -1)),
                }[f]
                out.append((p, n))
    return out


def _rotate(v, axis, direction):
    x, y, z = v
    return ((x, -direction*z, direction*y),
            (direction*z, y, -direction*x),
            (-direction*y, direction*x, z))[axis]


def _permutations():
    geometry = _geometry()
    lookup = {g: i for i, g in enumerate(geometry)}
    result = {}
    for face, (axis, side) in {'U': (1, 1), 'D': (1, -1), 'R': (0, 1),
                               'L': (0, -1), 'F': (2, 1), 'B': (2, -1)}.items():
        quarter = list(range(54))
        for i, (p, n) in enumerate(geometry):
            if p[axis] == side:
                dest = lookup[(_rotate(p, axis, -side), _rotate(n, axis, -side))]
                quarter[dest] = i
        perm = tuple(range(54))
        for suffix in ('', '2', "'"):
            perm = tuple(perm[j] for j in quarter)
            result[face + suffix] = perm
    return result


PERMUTATIONS = _permutations()


def apply_move(state: str, move: str) -> str:
    try:
        permutation = PERMUTATIONS[move]
    except (KeyError, TypeError) as exc:
        raise ValueError(f'Invalid move: {move!r}') from exc
    return ''.join([state[i] for i in permutation])


def apply_moves(state: str, moves: Iterable[str]) -> str:
    for move in moves:
        state = apply_move(state, move)
    return state


def is_solved(state: str) -> bool:
    return len(state) == 54 and all(len(set(state[i:i+9])) == 1 for i in range(0, 54, 9))


def invert_move(move: str) -> str:
    if move not in PERMUTATIONS:
        raise ValueError(f'Invalid move: {move!r}')
    return move if move.endswith('2') else move[0] if move.endswith("'") else move + "'"


def invert_moves(moves: Iterable[str]) -> list[str]:
    return [invert_move(m) for m in reversed(list(moves))]


def pretty_net(state: str) -> str:
    rows = ['      ' + ' '.join(state[r*3:r*3+3]) for r in range(3)]
    rows += ['  '.join(' '.join(state[f*9+r*3:f*9+r*3+3]) for f in (4, 2, 1, 5)) for r in range(3)]
    rows += ['      ' + ' '.join(state[27+r*3:30+r*3]) for r in range(3)]
    return '\n'.join(rows)


def self_test() -> None:
    unique = ''.join(chr(0x100+i) for i in range(54))
    for m in MOVES:
        if sorted(PERMUTATIONS[m]) != list(range(54)):
            raise RuntimeError(f'Nonbijective permutation: {m}')
        if apply_moves(unique, [m, invert_move(m)]) != unique:
            raise RuntimeError(f'Inverse self-test failed: {m}')
    for face in FACES:
        if apply_moves(unique, [face]*4) != unique or apply_moves(unique, [face+'2']*2) != unique:
            raise RuntimeError(f'Order self-test failed: {face}')
    # Independent standard facelet vector, not derived from our geometry.
    expected_r = 'UUFUUFUUFRRRRRRRRRFFDFFDFFDDDBDDBDDBLLLLLLLLLUBBUBBUBB'
    if apply_move(solved_state(), 'R') != expected_r:
        raise RuntimeError('Standard R vector failed')
    if apply_moves(unique, ['R', 'U', "R'", "U'"]*6) != unique:
        raise RuntimeError('Commutator self-test failed')
