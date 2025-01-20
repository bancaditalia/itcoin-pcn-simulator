"""This module contains model classses and functions for the plasma network generation library."""

import dataclasses
import re
from collections import Counter
from collections.abc import Collection
from enum import Enum

from plasma_network_generator.utils import EU_COUNTRY_CODE, float_between_0_and_1

NATION_NAME_REGEX = re.compile(r"[A-Z]+")
_APPROXIMATION_DIGITS = 9


class NodeType(Enum):
    CENTRAL_BANK = "Central Bank node"
    INTERMEDIARY = "Intermediary node"
    RETAIL_BANKED = "Retail node (banked)"
    RETAIL_UNBANKED = "Retail node (unbanked)"
    MERCHANT_SMALL = "Merchant small"
    MERCHANT_MEDIUM = "Merchant medium"
    MERCHANT_LARGE = "Merchant large"

    def is_retail(self):
        """Return True if the node is a retail node."""
        return self in (NodeType.RETAIL_BANKED, NodeType.RETAIL_UNBANKED)

    def is_merchant(self):
        """Return True if the node is a merchant node."""
        return self in (
            NodeType.MERCHANT_SMALL,
            NodeType.MERCHANT_MEDIUM,
            NodeType.MERCHANT_LARGE,
        )

    def is_user(self) -> bool:
        """Return True if the node is a user."""
        return self.is_retail() or self.is_merchant()


class ChannelType(Enum):
    NATIONAL = "national"
    INTERNATIONAL = "international"


class SubnetworkType(Enum):
    S_1_CHANNEL_1 = "[1<channel>1]"
    S_1_CHANNEL_2 = "[1<channel>2]"
    S_2_CHANNEL_2 = "[2<channel>2]"
    S_3_CHANNEL_3 = "[3<channel>3]"
    S_2_CHANNEL_3B = "[2<channel>3B]"
    S_2_CHANNEL_3M_SMALL = "[2<channel>3Msmall]"
    S_2_CHANNEL_3M_MEDIUM = "[2<channel>3Mmedium]"
    S_2_CHANNEL_3M_LARGE = "[2<channel>3Mlarge]"


@dataclasses.dataclass(frozen=True, slots=True)
class NationSpec:
    """Model the specification of a nation."""

    name: str
    relative_size: float

    def __post_init__(self) -> None:
        """Check that the nation name is valid."""
        assert re.fullmatch(
            NATION_NAME_REGEX,
            self.name,
        ), f"{self.name} is not a valid nation name"

    @classmethod
    def from_string(cls, s: str) -> "NationSpec":
        """Parse and check the given nation specification string.

        A 'nation specification' string is of the following form: '<name>,<relative_size>'
        """
        try:
            tokens = re.split(r":", s)
            assert len(tokens) == 2, (
                "the nation specification string must be of 2 tokens"
            )
            name, relative_size_str = tokens
            assert re.fullmatch(r"[A-Z]+", name), f"{name} is not a valid nation name"
            assert name != EU_COUNTRY_CODE, "the EU country code is reserved"
            relative_size = float_between_0_and_1(relative_size_str)
            return cls(name, relative_size)  # type: ignore
        except AssertionError as e:
            msg = f"{s} is not a valid nation specification string: {e}"
            raise ValueError(msg) from None


@dataclasses.dataclass(frozen=True, slots=True)
class NationSpecs:
    """Container class of nation size specifications indexed by nation name."""

    specs_by_name: dict[str, NationSpec]

    def __post_init__(self) -> None:
        """Run post-initialization checks."""
        assert len(self.specs_by_name) > 0, "the nation specs must not be empty"
        assert (
            self._round(
                sum([spec.relative_size for spec in self.specs_by_name.values()]),
            )
            == 1.0
        ), "the sum of the relative sizes of the nations must be 1.0"

    @property
    def nations(self) -> set[str]:
        """Return the list of nation names."""
        return set(self.specs_by_name.keys())

    @property
    def nb_nations(self) -> int:
        """Return the number of nations."""
        return len(self.specs_by_name)

    def get_spec(self, nation_id: str) -> NationSpec:
        """Return the NationSpec instance for the given nation id."""
        try:
            return self.specs_by_name[nation_id]
        except KeyError:
            msg = f"unknown nation id: {nation_id}"
            raise ValueError(msg) from None

    @classmethod
    def from_sequence(cls, seq: list[NationSpec]) -> "NationSpecs":
        """Create a NationSpecs instance from a sequence of NationSpec."""
        # check duplicates
        names_count = Counter(spec.name for spec in seq)
        duplicates = [name for name, count in names_count.items() if count > 1]
        assert len(duplicates) == 0, "duplicate nation names: " + ", ".join(duplicates)

        return cls({spec.name: spec for spec in seq})

    @classmethod
    def from_nation_list(cls, nation_list: Collection[str]) -> "NationSpecs":
        """Create a NationSpecs instance from a nation list string.

        It gives equal relative size to all nations.
        """
        nation_spec_list = []
        for nation_name in nation_list:
            nation_spec_list.append(NationSpec(nation_name, 1.0 / len(nation_list)))
        return cls.from_sequence(nation_spec_list)

    def _round(self, f: float) -> float:
        """Round the given float to the number of approximation digits."""
        return round(f, ndigits=_APPROXIMATION_DIGITS)

    def override(self, overrides: dict[str, NationSpec]) -> "NationSpecs":
        """Return a new NationSpecs instance with the given overrides."""
        # check that the overrides are valid
        unknown_keys = set(overrides.keys()) - set(self.specs_by_name.keys())
        if len(unknown_keys) > 0:
            msg = f"the following nation ids are not in the original nation specs: {sorted(unknown_keys)}"
            raise ValueError(msg)

        if not all(0.0 <= v.relative_size <= 1.0 for v in overrides.values()):
            msg = "the relative sizes of the nations in the overrides must be between 0.0 and 1.0"
            raise ValueError(msg)
        relative_fixed_amount = sum(s.relative_size for s in overrides.values())
        if relative_fixed_amount > 1.0:
            msg = f"the sum of the relative sizes of the nations in the overrides is greater than 1.0: {relative_fixed_amount}"
            raise ValueError(msg)

        # the relative size of the nations not in the overrides is computed with the remaining amount available
        relative_remaining_amount = max(1.0 - relative_fixed_amount, 0.0)

        # the relative size of the nations in the overrides is hard-coded
        non_overrides_unity = sum(
            [
                self._round(v.relative_size)
                for k, v in self.specs_by_name.items()
                if k not in overrides
            ],
        )
        scaling_factor = relative_remaining_amount / non_overrides_unity
        new_relative_sizes_by_name = {
            k: NationSpec(k, self._round(v.relative_size) * scaling_factor)
            for k, v in self.specs_by_name.items()
            if k not in overrides
        } | overrides
        return NationSpecs(new_relative_sizes_by_name)


def get_eurosystem_population_by_country() -> dict[str, int]:
    """Return the list of eurosystem countries with their absolute population.

    The data dates back to 2023-01-01 and are taken from:
     https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Population_and_population_change_statistics
    """
    return {
        "AT": 9_104_772,
        "BE": 11_754_004,
        "CY": 920_701,
        "DE": 84_358_845,
        "EE": 1_365_884,
        "ES": 48_059_777,
        "FI": 5_563_970,
        "FR": 68_070_697,
        "GR": 10_394_055,
        "HR": 3_850_894,
        "IE": 5_194_336,
        "IT": 58_850_717,
        "LT": 2_857_279,
        "LU": 660_809,
        "LV": 1_883_008,
        "MT": 542_051,
        "NL": 17_811_291,
        "PT": 10_467_366,
        "SI": 2_116_792,
        "SK": 5_428_792,
    }


def get_eurosystem_nation_specs() -> NationSpecs:
    """Return the NationSpecs instance for the eurosystem."""
    eurosystem_population_by_country = get_eurosystem_population_by_country()
    total_population = sum(eurosystem_population_by_country.values())
    return NationSpecs(
        {
            k: NationSpec(k, v / total_population)
            for k, v in eurosystem_population_by_country.items()
        },
    )


def select_eurosystem_subset(
    nations: Collection[str],
) -> NationSpecs:
    """Return a subset of the eurosystem nations and renormalize wrt the given relative size."""
    nations = set(nations)
    eurosystem_nation_specs = get_eurosystem_nation_specs()
    eurosystem_nations = eurosystem_nation_specs.nations
    assert nations.issubset(
        eurosystem_nations,
    ), (
        f"the given nations must be a subset of the eurosystem nations: {nations - eurosystem_nations}"
    )

    # renormalize wrt the given relative size
    relative_size = sum(
        eurosystem_nation_specs.get_spec(n).relative_size for n in nations
    )
    subset_nation_spec = {
        n: NationSpec(
            n,
            eurosystem_nation_specs.get_spec(n).relative_size / relative_size,
        )
        for n in nations
    }
    assert (
        round(
            sum(spec.relative_size for spec in subset_nation_spec.values()),
            ndigits=8,
        )
        == 1.0
    )
    return NationSpecs(subset_nation_spec)
