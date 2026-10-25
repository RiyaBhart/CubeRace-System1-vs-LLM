import random
import pytest
from backend.cube_engine import (FACES, MOVES, PERMUTATIONS, apply_move, apply_moves,
    deserialize, invert_move, invert_moves, is_solved, pretty_net, self_test, serialize, solved_state)
from backend.scramble import OPPOSITE, generate_scramble, puzzle


@pytest.mark.parametrize('move', MOVES)
def test_inverse_and_bijection(move):
    unique = ''.join(chr(0x100+i) for i in range(54))
    assert apply_moves(unique, [move, invert_move(move)]) == unique
    assert sorted(PERMUTATIONS[move]) == list(range(54))
    assert apply_move(solved_state(), move) != solved_state()
    assert all(apply_move(unique, move)[9*i+4] == unique[9*i+4] for i in range(6))


@pytest.mark.parametrize('face', FACES)
def test_move_orders(face):
    s = puzzle(20, 7)[1]
    assert apply_moves(s, [face]*4) == s
    assert apply_moves(s, [face+'2']*2) == s
    assert apply_moves(s, [face]*2) == apply_move(s, face+'2')


def test_independent_vectors():
    self_test()
    assert apply_move(solved_state(), 'U') == 'UUUUUUUUUBBBRRRRRRRRRFFFFFFDDDDDDDDDFFFLLLLLLLLLBBBBBB'
    assert apply_moves(solved_state(), ['R','U',"R'","U'"]*6) == solved_state()


@pytest.mark.parametrize('length', [0, 3, 4, 5, 15, 20])
def test_scrambles(length):
    for seed in range(20):
        moves, state = puzzle(length, seed)
        assert moves == generate_scramble(length, seed)
        assert len(moves) == length
        assert apply_moves(state, invert_moves(moves)) == solved_state()
        assert all(a[0] != b[0] for a,b in zip(moves,moves[1:]))
        assert all(not (a[0] == c[0] and OPPOSITE[a[0]] == b[0]) for a,b,c in zip(moves,moves[1:],moves[2:]))


def test_serialization_validation_and_net():
    assert serialize(deserialize(solved_state())) == solved_state()
    assert is_solved(solved_state())
    assert len(pretty_net(solved_state()).splitlines()) == 9
    for bad in ['', 'x'*54, solved_state()[:-1]]:
        with pytest.raises(ValueError):
            deserialize(bad)
    with pytest.raises(ValueError):
        apply_move(solved_state(), 'r')
    with pytest.raises(ValueError):
        generate_scramble(-1, 1)


def test_global_rng_not_modified():
    random.seed(12)
    previous = random.getstate()
    generate_scramble(20, 6)
    assert random.getstate() == previous
