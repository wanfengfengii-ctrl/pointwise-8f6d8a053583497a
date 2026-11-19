from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from survey.junctions import require_name
from survey.roads import Road


@dataclass(frozen=True, slots=True)
class Restriction:
    id: str
    roads: tuple[str, str, str]


def validate_restrictions(
    restrictions: Iterable[Restriction], roads: Mapping[str, Road]
) -> tuple[Restriction, ...]:
    by_id = {}
    for restriction in restrictions:
        if not isinstance(restriction, Restriction):
            raise ValueError('expected a Restriction')
        name = require_name(restriction.id, 'restriction id')
        sequence = restriction.roads
        if not isinstance(sequence, (list, tuple)) or len(sequence) != 3:
            raise ValueError(f'restriction {name!r} must identify three roads')
        ids = tuple(require_name(road, 'restriction road') for road in sequence)
        if name in by_id:
            raise ValueError(f'duplicate restriction {name!r}')
        if any(road_id not in roads for road_id in ids):
            raise ValueError(f'unknown road in restriction {name!r}')
        first, middle, last = (roads[road_id] for road_id in ids)
        if first.end != middle.start or middle.end != last.start:
            raise ValueError(f'restriction {name!r} is not a continuous directed passage')
        by_id[name] = Restriction(name, ids)
    return tuple(by_id[name] for name in sorted(by_id))
