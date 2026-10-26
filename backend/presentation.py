"""Shared decision information; this module never imports an exact solver."""
from .cube_engine import FACES, DEFINITIONS, apply_move, pretty_net, solved_state

PRESENTATION_VERSION = 'oriented-color-net-v3'
COLORS = dict(zip(FACES, ('white', 'red', 'green', 'yellow', 'orange', 'blue')))
# Top and right edge neighbours fix each externally viewed face orientation.
ORIENTATION = {'U': ('B', 'R'), 'R': ('U', 'B'), 'F': ('U', 'R'),
               'D': ('F', 'R'), 'L': ('U', 'F'), 'B': ('U', 'L')}
INSTRUCTIONS = ('Choose one move toward the goal. Facelets: row-major URFDLB, fixed centers. '
                'Singmaster turns: clockwise viewed directly at the named face. '
                'Half-turn metric (HTM): 180 degrees counts as one move. Limit: 30 moves. '
                'Avoid immediately undoing the previous move unless you have a reason. '
                'Return one legal move; do not output explanations.')


def shared_context(state, recent_moves, allowed_moves, *, max_moves=30, history_length=-1, condition='pure'):
    if condition not in ('pure', 'assisted'):
        raise ValueError('Unknown experimental condition')
    history = recent_moves if history_length == -1 else recent_moves[-history_length:] if history_length else []
    faces, correct = {}, {}
    for index, face in enumerate(FACES):
        stickers = state[index*9:index*9+9]
        top, right = ORIENTATION[face]
        faces[face] = {'top_edge': top, 'right_edge': right,
                       'rows': [[COLORS[c] for c in stickers[r*3:r*3+3]] for r in range(3)]}
        correct[face] = stickers.count(face)
    context = {'cube_facelets': state, 'recent_moves': list(history),
        'history_policy': 'all' if history_length == -1 else f'last {history_length} legal moves',
        'goal_facelets': solved_state(), 'moves_remaining': max(0, max_moves-len(recent_moves)),
        'metric': 'HTM', 'condition': condition,
        'centers': 'Centers never move and define each face color.', 'colors': COLORS,
        'faces': faces, 'net_layout': 'U above F; L F R B across; D below F. All rows viewed from outside.',
        'net': pretty_net(state), 'correct_facelets': {'per_face': correct, 'total': sum(correct.values()), 'of': 54},
        # Outside-face wording adapted from Srijaali/ai-engineering; see THIRD_PARTY.md.
        'criteria': {m: DEFINITIONS[m] + ', viewed directly from outside that face.' for m in allowed_moves}}
    def row(face, r):
        i = FACES.index(face)*9+r*3
        return ' '.join(COLORS[c] for c in state[i:i+3])
    context['net'] = '\n'.join(
        ['                  U: ' + row('U', r) for r in range(3)] +
        [' | '.join(f + ': ' + row(f, r) for f in 'LFRB') for r in range(3)] +
        ['                  D: ' + row('D', r) for r in range(3)])
    if condition == 'assisted':
        context['one_step_correct_facelets'] = {
            m: sum(a == b for a, b in zip(apply_move(state, m), solved_state())) for m in allowed_moves}
    return context


def instruction(max_moves=30):
    return INSTRUCTIONS.replace('Limit: 30 moves.', f'Limit: {max_moves} moves.')
