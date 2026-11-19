from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from survey.junctions import Junction, require_name


@dataclass(frozen=True, slots=True)
class Road:
    id: str
    start: str
    end: str
    cost: int


def index_roads(roads: Iterable[Road], junctions: Mapping[str, Junction]) -> dict[str, Road]:
    indexed = {}
    for road in roads:
        if not isinstance(road, Road):
            raise ValueError('expected a Road')
        name = require_name(road.id, 'road id')
        start = require_name(road.start, 'road start')
        end = require_name(road.end, 'road end')
        if start not in junctions or end not in junctions:
            raise ValueError(f'unknown junction on road {name!r}')
        if type(road.cost) is not int or road.cost <= 0:
            raise ValueError(f'road {name!r} must have a positive integer cost')
        if name in indexed:
            raise ValueError(f'duplicate road {name!r}')
        indexed[name] = road
    return indexed


def encode_cost(cost: int) -> str:
    if type(cost) is not int:
        raise ValueError('cost must be an integer')
    return hex(cost)


def decode_cost(value: object) -> int:
    if not isinstance(value, str):
        raise ValueError('encoded cost must be hexadecimal text')
    cost = int(value, 16)
    if encode_cost(cost) != value:
        raise ValueError('cost must use canonical hexadecimal encoding')
    return cost
