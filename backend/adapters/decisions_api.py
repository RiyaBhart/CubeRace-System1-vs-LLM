"""Alpha schema boundary. Edit build_request and parse_response when API changes.

Source checked: OpenRouterTeam/skills, references/decisions-api.md.
Fixture variants are synthetic contract examples, not claimed live recordings.
"""
import math
from .base import INSTRUCTIONS, OpenRouterAdapter, shared_context
from ..presentation import instruction

URL = 'https://openrouter.ai/api/alpha/decisions'


def build_request(model: str, state: str, recent: list[str], allowed: tuple[str, ...], *, max_moves=30, history_length=-1, condition='pure', attempts_used=None) -> dict:
    context = shared_context(state, recent, allowed, max_moves=max_moves, history_length=history_length, condition=condition, attempts_used=attempts_used)
    # Definitions occur once, in criteria. Other state fields match chat content.
    criteria = context.pop('criteria')
    return {'model': model, 'state': context, 'questions': {'next_move': {
        'type': 'choice', 'instructions': instruction(max_moves), 'criteria': criteria}}}


def parse_response(raw: dict, allowed: tuple[str, ...]) -> tuple[str, float | None]:
    """Documented answers shape first; explicit alternative containers only.

    Never choose argmax of probabilities: missing choice is an invalid output.
    Conflicting supported shapes are rejected rather than silently selected.
    """
    if not isinstance(raw, dict):
        raise ValueError('Expected JSON object')
    answers = []
    for key in ('answers', 'decisions', 'results', 'questions'):
        container = raw.get(key)
        if isinstance(container, dict) and 'next_move' in container:
            answers.append(container['next_move'])
    if 'next_move' in raw:
        answers.append(raw['next_move'])
    if len(answers) != 1:
        raise ValueError('Missing or ambiguous next_move answer')
    answer = answers[0]
    confidence = None
    if isinstance(answer, dict):
        if answer.get('type', 'choice') != 'choice':
            raise ValueError('Expected choice answer')
        options = [answer[k] for k in ('choice', 'selected', 'value', 'option') if k in answer]
        if len(options) != 1:
            raise ValueError('Missing or ambiguous selected option')
        move = options[0]
        confidence = answer.get('confidence')
        if confidence is None and isinstance(answer.get('probabilities'), dict) and isinstance(move, str):
            confidence = answer['probabilities'].get(move)
    else:
        move = answer
    if not isinstance(move, str) or move not in allowed:
        raise ValueError('Invalid selected move')
    if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                                   or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        confidence = None
    return move, confidence


class DecisionsAdapter(OpenRouterAdapter):
    def request(self, state, recent, allowed):
        return URL, build_request(self.model.id, state, recent, allowed, max_moves=self.settings.max_moves,
                                  history_length=self.settings.history_length, condition=self.settings.condition,
                                  attempts_used=self.attempts_used)

    def parse(self, raw, allowed):
        return parse_response(raw, allowed)
