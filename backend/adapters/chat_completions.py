import json
from .base import INSTRUCTIONS, IncompleteOutput, OpenRouterAdapter, shared_context
from ..presentation import instruction

URL = 'https://openrouter.ai/api/v1/chat/completions'


def unique_object(pairs):
    """Reject duplicate keys. Adapted with permission; see THIRD_PARTY.md."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def parse_response(raw: dict, allowed: tuple[str, ...]) -> tuple[str, None]:
    choice = raw['choices'][0]
    if choice.get('finish_reason') == 'length' or choice.get('native_finish_reason') == 'max_tokens':
        raise IncompleteOutput('Completion token ceiling reached before a complete move; no retry or limit increase was performed')
    content = choice['message']['content']
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Model returned no move JSON')
    # Strict parsing remains mandatory even if a provider violates the schema.
    parsed = json.loads(content, object_pairs_hook=unique_object)
    if not isinstance(parsed, dict) or set(parsed) != {'move'}:
        raise ValueError('Expected exactly one move property')
    if not isinstance(parsed['move'], str) or parsed['move'] not in allowed:
        raise ValueError('Invalid move')
    return parsed['move'], None


class ChatAdapter(OpenRouterAdapter):
    def parse(self, raw, allowed):
        return parse_response(raw, allowed)

    def request(self, state, recent, allowed):
        context = {'instructions': instruction(self.settings.max_moves), **shared_context(state, recent, allowed,
            max_moves=self.settings.max_moves, history_length=self.settings.history_length, condition=self.settings.condition,
            attempts_used=self.attempts_used)}
        # Opus 5.5 removed temperature/top_p/top_k. Sending temperature=0
        # excludes every endpoint under require_parameters=True (HTTP 404).
        body = {'model': self.model.id,
                'max_tokens': self.settings.claude_max_tokens,
                'reasoning': {'effort': self.settings.claude_reasoning_effort},
                'usage': {'include': True},
                'provider': {'require_parameters': True},
                'messages': [
                    {'role': 'system', 'content': 'Return one legal move as schema JSON.'},
                    {'role': 'user', 'content': json.dumps(context, separators=(',', ':'))}]}
        body['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'next_move', 'strict': True, 'schema': {
                    'type': 'object', 'properties': {'move': {'type': 'string', 'enum': list(allowed)}},
                    'required': ['move'], 'additionalProperties': False}}}
        return URL, body
