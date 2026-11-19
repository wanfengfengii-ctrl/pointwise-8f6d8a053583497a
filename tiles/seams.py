from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from survey.junctions import require_name


@dataclass(frozen=True, slots=True)
class SeamKey:
    road_id: str
    id: str


@dataclass(frozen=True, slots=True)
class Seam:
    key: SeamKey
    x: int
    y: int


Endpoint = str | SeamKey


def index_seams(seams: Iterable[Seam], roads: Mapping) -> dict[SeamKey, Seam]:
    indexed = {}
    for seam in seams:
        if not isinstance(seam, Seam) or not isinstance(seam.key, SeamKey):
            raise ValueError('expected a seam with a road-scoped key')
        require_name(seam.key.road_id, 'seam road')
        require_name(seam.key.id, 'seam name')
        if seam.key.road_id not in roads:
            raise ValueError(f'unknown owner of seam {seam.key!r}')
        if type(seam.x) is not int or type(seam.y) is not int:
            raise ValueError('seam coordinates must be integers')
        if seam.key in indexed:
            raise ValueError(f'duplicate seam {seam.key!r}')
        indexed[seam.key] = seam
    return indexed


def validate_seam_continuation(
    road_id: str, outgoing: Endpoint, incoming: Endpoint, seams: Mapping[SeamKey, Seam]
) -> SeamKey:
    if not isinstance(outgoing, SeamKey) or not isinstance(incoming, SeamKey):
        raise ValueError(f'interior continuation of {road_id!r} requires an artificial seam')
    if outgoing != incoming or outgoing.road_id != road_id or outgoing not in seams:
        raise ValueError(f'broken or foreign seam on road {road_id!r}')
    return outgoing
