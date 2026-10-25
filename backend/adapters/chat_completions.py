import json
from .base import INSTRUCTIONS, OpenRouterAdapter, shared_context

URL = 'https://openrouter.ai/api/v1/chat/completions'


def parse_response(raw: dict, allowed: tuple[str, ...]) -> tuple[str, None]:
    content = raw['choices'][0]['message']['content']
    # Strict parsing remains mandatory even if a provider violates the schema.
    parsed = json.loads(content)
    if not isinstance(parsed, dict) or set(parsed) != {'move'}:
        raise ValueError('Expected exactly one move property')
    if not isinstance(parsed['move'], str) or parsed['move'] not in allowed:
        raise ValueError('Invalid move')
    return parsed['move'], None


class ChatAdapter(OpenRouterAdapter):
    def parse(self, raw, allowed):
        return parse_response(raw, allowed)

    def request(self, state, recent, allowed):
        context = {'instructions': INSTRUCTIONS, **shared_context(state, recent, allowed)}
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
