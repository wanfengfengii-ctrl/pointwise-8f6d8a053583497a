from collections.abc import Iterable
from dataclasses import dataclass

from survey.junctions import Junction, index_junctions
from survey.restrictions import Restriction, validate_restrictions
from survey.revision_store import RevisionStore
from survey.roads import Road, index_roads


@dataclass(frozen=True, slots=True)
class Revision:
    id: int
    junctions: tuple[Junction, ...]
    roads: tuple[Road, ...]
    restrictions: tuple[Restriction, ...]


def save_revision(
    store: RevisionStore,
    junctions: Iterable[Junction],
    roads: Iterable[Road],
    restrictions: Iterable[Restriction],
) -> int:
    try:
        junction_index = index_junctions(junctions)
        road_index = index_roads(roads, junction_index)
        rules = validate_restrictions(restrictions, road_index)
    except TypeError as error:
        raise ValueError('revision inputs must contain junctions, roads and restrictions') from error
    return store.commit(
        tuple(junction_index[name] for name in sorted(junction_index)),
        tuple(road_index[name] for name in sorted(road_index)),
        rules,
    )


def load_revision(store: RevisionStore, revision_id: int) -> Revision:
    snapshot = store.get(revision_id)
    if snapshot is None:
        raise KeyError(revision_id)
    return Revision(revision_id, *snapshot)
