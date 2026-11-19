from collections import defaultdict
from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass

from survey.junctions import require_name
from survey.roads import Road
from tiles.seams import Endpoint, Seam, SeamKey, validate_seam_continuation


FragmentRef = tuple[str, str]


@dataclass(frozen=True, slots=True)
class Fragment:
    id: str
    road_id: str
    tile_id: str
    ordinal: int
    start: Endpoint
    end: Endpoint
    cost: int

    @property
    def ref(self) -> FragmentRef:
        return self.tile_id, self.id


@dataclass(frozen=True, slots=True)
class FragmentChain:
    road_id: str
    fragments: tuple[Fragment, ...]

    @property
    def refs(self) -> tuple[FragmentRef, ...]:
        return tuple(fragment.ref for fragment in self.fragments)


def assemble_fragment_chains(fragments: Iterable[Fragment]) -> tuple[FragmentChain, ...]:
    groups = defaultdict(list)
    seen = set()
    for fragment in fragments:
        if not isinstance(fragment, Fragment):
            raise ValueError('expected a Fragment')
        require_name(fragment.id, 'fragment id')
        require_name(fragment.road_id, 'fragment road')
        require_name(fragment.tile_id, 'fragment tile')
        if type(fragment.ordinal) is not int or fragment.ordinal < 0:
            raise ValueError('fragment ordinal must be a nonnegative integer')
        if type(fragment.cost) is not int:
            raise ValueError('fragment cost must be an integer')
        for endpoint in (fragment.start, fragment.end):
            if isinstance(endpoint, SeamKey):
                require_name(endpoint.road_id, 'endpoint seam road')
                require_name(endpoint.id, 'endpoint seam name')
            else:
                require_name(endpoint, 'fragment junction')
        if fragment.ref in seen:
            raise ValueError(f'duplicate tile fragment {fragment.ref!r}')
        seen.add(fragment.ref)
        groups[fragment.road_id].append(fragment)
    return tuple(
        FragmentChain(road_id, tuple(sorted(groups[road_id], key=lambda part: part.ordinal)))
        for road_id in sorted(groups)
    )


def validate_fragment_chains(
    roads: Mapping[str, Road],
    tiles: Set[str],
    seams: Mapping[SeamKey, Seam],
    chains: Iterable[FragmentChain],
) -> None:
    represented = set()
    used_seams = set()
    for chain in chains:
        road = roads.get(chain.road_id)
        if road is None or chain.road_id in represented or not chain.fragments:
            raise ValueError(f'invalid fragment chain for road {chain.road_id!r}')
        represented.add(chain.road_id)
        first, last = chain.fragments[0], chain.fragments[-1]
        if first.start != road.start or last.end != road.end:
            raise ValueError(f'incomplete or reversed fragment chain for road {road.id!r}')
        for ordinal, fragment in enumerate(chain.fragments):
            if fragment.road_id != road.id or fragment.ordinal != ordinal:
                raise ValueError(f'invalid fragment order or ownership on road {road.id!r}')
            if fragment.tile_id not in tiles:
                raise ValueError(f'unknown tile on fragment {fragment.ref!r}')
            if ordinal:
                previous = chain.fragments[ordinal - 1]
                seam = validate_seam_continuation(road.id, previous.end, fragment.start, seams)
                if seam in used_seams:
                    raise ValueError(f'seam {seam!r} is reused within its directed chain')
                used_seams.add(seam)
    if represented != set(roads):
        raise ValueError('layout does not cover exactly the original directed roads')
    if used_seams != set(seams):
        raise ValueError('layout contains unused seam declarations')
