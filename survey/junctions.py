from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Junction:
    id: str


def require_name(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonblank name')
    return value


def index_junctions(junctions: Iterable[Junction]) -> dict[str, Junction]:
    indexed = {}
    for junction in junctions:
        if not isinstance(junction, Junction):
            raise ValueError('expected a Junction')
        name = require_name(junction.id, 'junction id')
        if name in indexed:
            raise ValueError(f'duplicate junction {name!r}')
        indexed[name] = junction
    return indexed
