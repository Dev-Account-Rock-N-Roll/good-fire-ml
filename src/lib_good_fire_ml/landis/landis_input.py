from collections.abc import Iterator
from dataclasses import dataclass, field
import enum
import io
import shlex

import numpy as np
import rasterio

# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================


class PostFireRegeneration(enum.Enum):
    NONE = "none"
    RESPROUT = "resprout"
    SEROTINY = "serotiny"

    @classmethod
    def from_string(cls, value: str) -> PostFireRegeneration:
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid post-fire regeneration: {value}. Valid values: none, resprout, serotiny."
            )


UNIVERSAL_SEED_DISTANCE = -1


# =============================================================================
# DOMAIN MODELS (Data Structures & Validation)
# =============================================================================


@dataclass
class Species:
    name: str
    longevity: int
    maturity: int
    shade_tolerance: int
    fire_tolerance: int
    effective_seed_distance: int
    max_seed_distance: int
    vegetative_reproduction_probability: float
    min_sprout_age: int
    max_sprout_age: int
    post_fire_regeneration: PostFireRegeneration

    def __post_init__(self):
        """Validates species parameters based on the original C# rules."""
        if self.longevity < 0:
            raise ValueError(f"[{self.name}] Longevity must be >= 0.")
        if self.maturity < 0 or self.maturity > self.longevity:
            raise ValueError(
                f"[{self.name}] Maturity ({self.maturity}) must be >= 0 "
                f"and <= longevity ({self.longevity})."
            )

        if not (1 <= self.shade_tolerance <= 5):
            raise ValueError(f"[{self.name}] Shade tolerance must be between 1 and 5.")
        if not (1 <= self.fire_tolerance <= 5):
            raise ValueError(f"[{self.name}] Fire tolerance must be between 1 and 5.")

        if self.effective_seed_distance != UNIVERSAL_SEED_DISTANCE:
            if self.effective_seed_distance <= 0:
                raise ValueError(f"[{self.name}] Effective seed distance must be > 0.")
            if self.max_seed_distance < self.effective_seed_distance:
                raise ValueError(
                    f"[{self.name}] Max seed distance ({self.max_seed_distance}) "
                    f"must be >= effective seed distance ({self.effective_seed_distance})."
                )

        if self.max_seed_distance < 0:
            raise ValueError(f"[{self.name}] Max seed distance must be >= 0.")

        if not (0.0 <= self.vegetative_reproduction_probability <= 1.0):
            raise ValueError(f"[{self.name}] Veg reprod probability must be between 0.0 and 1.0.")

        if self.min_sprout_age < 0 or self.min_sprout_age > self.longevity:
            raise ValueError(f"[{self.name}] Min sprout age must be >= 0 and <= longevity.")
        if self.max_sprout_age < 0 or self.max_sprout_age > self.longevity:
            raise ValueError(f"[{self.name}] Max sprout age must be >= 0 and <= longevity.")
        if self.max_sprout_age < self.min_sprout_age:
            raise ValueError(f"[{self.name}] Max sprout age must be >= min sprout age.")


@dataclass
class Ecoregion:
    active: bool
    map_code: int
    name: str
    description: str

    def __post_init__(self):
        if self.map_code < 0 or self.map_code > 65535:
            raise ValueError(f"[{self.name}] Map code must be between 0 and 65535.")


@dataclass
class Extension:
    name: str
    initialization_file: str


@dataclass
class Scenario:
    duration: int
    species_filepath: str
    ecoregions_filepath: str
    ecoregions_map_filepath: str
    cell_length: float | None = field(default=None)
    initial_communities_filepath: str | None = field(default=None)
    initial_communities_map_filepath: str | None = field(default=None)
    disturbances_random_order: bool = field(default=False)
    random_number_seed: int | None = field(default=None)
    extensions: list[Extension] = field(default_factory=list)


# =============================================================================
# TEXT PARSING FRAMEWORK
# =============================================================================


def _read_landis_lines(text_stream: io.TextIOBase) -> Iterator[list[str]]:
    """
    Generator that parses a Landis-II text stream.
    Strips line comments (>>), inline comments (<<), and skips empty lines.
    Yields lists of tokens using shlex to properly handle quoted strings.
    """
    for line in text_stream:
        # Strip inline comments
        if "<<" in line:
            line = line.split("<<")[0]
        # Strip line comments
        if ">>" in line:
            line = line.split(">>")[0]

        line = line.strip()
        if not line:
            continue

        # shlex safely breaks line into tokens, respecting quotes
        yield shlex.split(line)


def _validate_landis_data_header(tokens: list[str], expected_type: str):
    """Validates the 'LandisData <Type>' header mandatory for all input files."""
    if not tokens or tokens[0].lower() != "landisdata":
        raise ValueError("File must begin with the 'LandisData' variable.")
    if len(tokens) < 2 or tokens[1].lower() != expected_type.lower():
        raise ValueError(
            f"Expected LandisData type '{expected_type}', got '{tokens[1] if len(tokens) > 1 else 'None'}'."
        )


# =============================================================================
# SPECIFIC FILE PARSERS
# =============================================================================


def parse_scenario(text_stream: io.TextIOBase) -> Scenario:
    """Parses a Scenario text file."""
    lines = _read_landis_lines(text_stream)

    header_tokens = next(lines, [])
    _validate_landis_data_header(header_tokens, "Scenario")

    config: dict = {"extensions": []}

    # Standard keys map to Scenario dataclass fields
    known_keys = {
        "duration": ("duration", int),
        "species": ("species_filepath", str),
        "ecoregions": ("ecoregions_filepath", str),
        "ecoregionsmap": ("ecoregions_map_filepath", str),
        "celllength": ("cell_length", float),
        "initialcommunities": ("initial_communities_filepath", str),
        "initialcommunitiesmap": ("initial_communities_map_filepath", str),
        "disturbancesrandomorder": ("disturbances_random_order", lambda v: v.lower() == "yes"),
        "randomnumberseed": ("random_number_seed", int),
    }

    for tokens in lines:
        key = tokens[0].lower()
        if key in known_keys:
            if len(tokens) < 2:
                raise ValueError(f"Missing value for parameter '{tokens[0]}'.")

            field_name, type_converter = known_keys[key]
            try:
                config[field_name] = type_converter(tokens[1])
            except ValueError:
                raise ValueError(f"Invalid value '{tokens[1]}' for parameter '{tokens[0]}'.")
        else:
            # If not a known key, it is an extension (Plug-in mapping)
            if len(tokens) < 2:
                raise ValueError(f"Missing initialization file for extension '{tokens[0]}'.")
            config["extensions"].append(Extension(name=tokens[0], initialization_file=tokens[1]))

    return Scenario(**config)


def parse_species(text_stream: io.TextIOBase) -> list[Species]:
    """Parses a Species table text file."""
    lines = _read_landis_lines(text_stream)

    header_tokens = next(lines, [])
    _validate_landis_data_header(header_tokens, "Species")

    species_list = []
    for tokens in lines:
        if len(tokens) < 11:
            raise ValueError(
                f"Insufficient parameters for species '{tokens[0]}'. Expected 11, got {len(tokens)}."
            )

        effective_dist_str = tokens[5].lower()
        effective_seed_dist = (
            UNIVERSAL_SEED_DISTANCE if effective_dist_str == "uni" else int(effective_dist_str)
        )

        try:
            species = Species(
                name=tokens[0],
                longevity=int(tokens[1]),
                maturity=int(tokens[2]),
                shade_tolerance=int(tokens[3]),
                fire_tolerance=int(tokens[4]),
                effective_seed_distance=effective_seed_dist,
                max_seed_distance=int(tokens[6]),
                vegetative_reproduction_probability=float(tokens[7]),
                min_sprout_age=int(tokens[8]),
                max_sprout_age=int(tokens[9]),
                post_fire_regeneration=PostFireRegeneration.from_string(tokens[10]),
            )
            species_list.append(species)
        except ValueError as err:
            raise ValueError(f"Error parsing species '{tokens[0]}': {err}")

    return species_list


def parse_ecoregions(text_stream: io.TextIOBase) -> list[Ecoregion]:
    """Parses an Ecoregions table text file."""
    lines = _read_landis_lines(text_stream)

    header_tokens = next(lines, [])
    _validate_landis_data_header(header_tokens, "Ecoregions")

    ecoregions = []
    seen_map_codes = set()

    for tokens in lines:
        if len(tokens) < 4:
            raise ValueError(
                f"Insufficient parameters for ecoregion '{tokens[0] if tokens else 'Unknown'}'. Expected 4."
            )

        active_str = tokens[0].lower()
        if active_str not in ("yes", "no"):
            raise ValueError(f"Invalid active status '{active_str}'. Must be 'yes' or 'no'.")

        is_active = active_str == "yes"
        map_code = int(tokens[1])
        name = tokens[2]
        description = tokens[3]

        if map_code in seen_map_codes:
            raise ValueError(f"Map code {map_code} is repeated.")
        seen_map_codes.add(map_code)

        try:
            ecoregion = Ecoregion(
                active=is_active, map_code=map_code, name=name, description=description
            )
            ecoregions.append(ecoregion)
        except ValueError as err:
            raise ValueError(f"Error parsing ecoregion '{name}': {err}")

    return ecoregions


# =============================================================================
# RASTER PARSING (GIS Input files)
# =============================================================================


def read_ecoregions_map(filepath: str) -> tuple[np.ndarray, dict]:
    """
    Reads a raster map (e.g., .img, .tif, .gis) representing the ecoregions.
    Returns a numpy array representing the 2D grid of map codes and raster metadata.
    """
    with rasterio.open(filepath) as dataset:
        # Landis typically uses band 1 for the ecoregion codes
        ecoregion_array = dataset.read(1)
        metadata = dataset.meta.copy()

    return ecoregion_array, metadata
