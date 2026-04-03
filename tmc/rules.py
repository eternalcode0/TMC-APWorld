from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Any, TypeVar

from BaseClasses import CollectionState
from NetUtils import JSONMessagePart
from Options import Option
from rule_builder.field_resolvers import FieldResolver, FromOption
from rule_builder.rules import (
    And,
    CanReachLocation,
    False_,
    Filtered,
    Has,
    HasAll,
    HasAny,
    HasGroup,
    OptionFilter,
    Or,
    Rule,
    True_,
)
from typing_extensions import override
from worlds.AutoWorld import World

from .constants import GAME, TMCEvent, TMCItem, TMCLocation, TMCRegion, TMCTricks
from .dungeons import ELEMENTS
from .locations import get_location_map
from .options import (
    Biggoron,
    CoFKeyMultiplier,
    DHCAccess,
    DHCKeyMultiplier,
    DungeonItem,
    DungeonWarp,
    DWSKeyMultiplier,
    FoWKeyMultiplier,
    Goal,
    GoronJPPrices,
    PoWKeyMultiplier,
    RCKeyMultiplier,
    ToDKeyMultiplier,
    Tricks,
    WarpCoF,
    WarpDHC,
    WarpDWS,
    WarpFoW,
    WarpPoW,
    WarpToD,
    WeaponBomb,
    WeaponBow,
    WeaponGust,
    WeaponLantern,
    WindCrestClouds,
    WindCrestCrenel,
    WindCrestFalls,
    WindCrestMinish,
    WindCrestSmith,
    WindCrestSwamp,
)
from .regions import get_region_map

if TYPE_CHECKING:
    from . import MinishCapWorld

    TMinishCapWorld = TypeVar("TMinishCapWorld", bound=MinishCapWorld, contravariant=True)  # noqa: PLC0105
else:
    TMinishCapWorld = TypeVar("TMinishCapWorld")


ORDERED_SWORDS: list[str] = [
    TMCItem.SMITHS_SWORD,
    TMCItem.WHITE_SWORD_GREEN,
    TMCItem.WHITE_SWORD_RED,
    TMCItem.WHITE_SWORD_BLUE,
    TMCItem.FOUR_SWORD,
]
DUNGEON_CLEARS: list[str] = [
    TMCEvent.CLEAR_DWS,
    TMCEvent.CLEAR_COF,
    TMCEvent.CLEAR_FOW,
    TMCEvent.CLEAR_TOD,
    TMCEvent.CLEAR_RC,
    TMCEvent.CLEAR_POW,
]


@dataclasses.dataclass(frozen=True)
class FromMultiplierResolver(FieldResolver, game=GAME):
    required: int
    multiplier_option: type[Option[Any]]

    @override
    def resolve(self, world: World) -> int:
        return math.ceil(self.required / FromOption(self.multiplier_option).resolve(world))


@dataclasses.dataclass
class CanActivatePedestal(Rule[TMinishCapWorld], game=GAME):
    @override
    def _instantiate(self, world: MinishCapWorld) -> Rule.Resolved:
        options = world.options
        return self.Resolved(
            options.ped_elements.value,
            options.ped_swords.value,
            options.ped_dungeons.value,
            options.ped_figurines.value,
            bool(options.progressive_sword.value),
            player=world.player,
        )

    class Resolved(Rule.Resolved):
        elements: int
        swords: int
        dungeons: int
        figurines: int
        progressive_swords: bool

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            return (
                self._elements_rule(state)
                and self._swords_rule(state)
                and self._dungeons_rule(state)
                and self._figurines_rule(state)
            )

        def _elements_rule(self, state: CollectionState) -> bool:
            return True if self.elements == 0 else state.has_group("Elements", self.player, self.elements)

        def _swords_rule(self, state: CollectionState) -> bool:
            return (
                True
                if self.swords == 0
                else (
                    state.has(TMCItem.PROGRESSIVE_SWORD, self.player, self.swords)
                    or state.has(ORDERED_SWORDS[self.swords - 1], self.player)
                )
            )

        def _dungeons_rule(self, state: CollectionState) -> bool:
            return state.has_from_list(DUNGEON_CLEARS, self.player, self.dungeons)

        def _figurines_rule(self, state: CollectionState) -> bool:
            return state.has(TMCItem.FIGURINE, self.player, self.figurines)

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            items = []
            if self.elements > 0:
                items.extend(ELEMENTS)
            if self.swords > 0:
                items.append(TMCItem.PROGRESSIVE_SWORD)
                items.append(ORDERED_SWORDS[self.swords - 1])
            if self.dungeons > 0:
                items.extend(DUNGEON_CLEARS)
            if self.figurines > 0:
                items.append(TMCItem.FIGURINE)
            return {item: {id(self)} for item in items}

        @override
        def explain_json(self, state: CollectionState | None = None) -> list[JSONMessagePart]:
            parts: list[JSONMessagePart] = [
                {"type": "color", "color": "green" if state and self(state) else "salmon", "text": "Activate Pedestal"}
            ]
            if self.elements == 0 and self.swords == 0 and self.dungeons == 0 and self.figurines == 0:
                return parts
            # text elements from hereon are prefixed with space, not suffixed
            parts.append({"type": "text", "text": " with"})
            if self.elements > 0:
                parts.append(
                    {
                        "type": "color",
                        "color": "green" if state and self._elements_rule(state) else "salmon",
                        "text": f", {self.elements} Elements",
                    }
                )
            if self.swords > 0:
                if self.progressive_swords:
                    parts.append(
                        {
                            "type": "color",
                            "color": "green" if state and self._swords_rule(state) else "salmon",
                            "text": f", {self.swords} Progressive Swords",
                        }
                    )
                else:
                    parts.append(
                        {
                            "type": "color",
                            "color": "green" if state and self._swords_rule(state) else "salmon",
                            "text": f", {ORDERED_SWORDS[self.swords - 1]}",
                        }
                    )
            if self.dungeons > 0:
                parts.append(
                    {
                        "type": "color",
                        "color": "green" if state and self._dungeons_rule(state) else "salmon",
                        "text": f", {self.dungeons} Dungeons",
                    }
                )
            if self.figurines > 0:
                parts.append(
                    {
                        "type": "color",
                        "color": "green" if state and self._figurines_rule(state) else "salmon",
                        "text": f", {self.figurines} Figurines",
                    }
                )
            return parts


@dataclasses.dataclass
class CanPay(Rule[TMinishCapWorld], game=GAME):
    price: int | FieldResolver

    @override
    def _instantiate(self, world: MinishCapWorld) -> Rule.Resolved:
        wallet_count = [(100, 0), (300, 1), (500, 2), (999, 3)]
        needed_wallets = None
        for size, count in wallet_count:
            price = self.price.resolve(world) if isinstance(self.price, FieldResolver) else self.price
            if price <= size:
                needed_wallets = count
                break
        if needed_wallets is None:
            return False_().resolve(world)
        return Has(TMCItem.BIG_WALLET, needed_wallets).resolve(world)


@dataclasses.dataclass(frozen=True)
class BoolMapperResolver(FieldResolver, game=GAME):
    option: type[Option[int]]
    true: Any
    false: Any

    @override
    def resolve(self, world: World) -> Any:
        return self.true if FromOption(self.option).resolve(world) else self.false


@dataclasses.dataclass
class HasMaxHealth(Rule[TMinishCapWorld], game=GAME):
    hearts: int

    @override
    def _instantiate(self, world: MinishCapWorld):
        return self.Resolved(self.hearts, world.options.starting_hearts.value, player=world.player)

    class Resolved(Rule.Resolved):
        required_hearts: int
        starting_hearts: int

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            if self.starting_hearts >= self.required_hearts:
                return True

            heart_containers = state.count(TMCItem.HEART_CONTAINER, self.player)
            heart_pieces = state.count(TMCItem.HEART_PIECE, self.player)

            max_health = self.starting_hearts + heart_containers + (heart_pieces // 4)
            return max_health >= self.required_hearts

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            if self.starting_hearts >= self.required_hearts:
                return {}
            items = [TMCItem.HEART_CONTAINER, TMCItem.HEART_PIECE]
            return {item: {id(self)} for item in items}


@dataclasses.dataclass
class CanSplit(Rule[TMinishCapWorld], game=GAME):
    link_count: int
    allow_max: bool = False

    @override
    def _instantiate(self, world: MinishCapWorld) -> Rule.Resolved:
        swords = ORDERED_SWORDS[self.link_count :] if self.allow_max else [ORDERED_SWORDS[self.link_count]]
        return (can_spin & (Has(TMCItem.PROGRESSIVE_SWORD, self.link_count + 1) | HasAny(*swords))).resolve(world)


class StupidToDWestIceblock(Rule[TMinishCapWorld], game=GAME):
    @override
    def _instantiate(self, world: MinishCapWorld) -> Rule.Resolved:
        """
        ToD is stupid, getting to the west ice block needs special access rules based off what got placed at it.
        Item placement for this location only occurs in create_items stage.
        """
        west_item = world.get_location(TMCLocation.DROPLETS_ENTRANCE_B2_WEST_ICEBLOCK).item
        if (
            west_item is None
            or west_item.name is not TMCItem.BIG_KEY_TOD
            or world.options.dungeon_warp_tod.value != DungeonWarp.option_none
        ):
            return tod_four_key_rule.resolve(world)
        if (
            west_item.name is TMCItem.BIG_KEY_TOD
            and world.options.dungeon_small_keys.value is DungeonItem.option_own_dungeon
        ):
            return tod_one_key_rule.resolve(world)
        return False_().resolve(world)


dws_warp_not_blue_filter = [OptionFilter(WarpDWS, (0, 2), operator="in")]
dws_warp_blue_filter = [OptionFilter(WarpDWS, (1, 3), operator="in")]
dws_warp_not_red_filter = [OptionFilter(WarpDWS, (0, 1), operator="in")]
dws_warp_red_filter = [OptionFilter(WarpDWS, (2, 3), operator="in")]
dws_warp_either_filter = [OptionFilter(WarpDWS, 0, operator="ne")]
dws_warp_neither_filter = [OptionFilter(WarpDWS, 0, operator="eq")]
dws_warp_both_filter = [OptionFilter(WarpDWS, 3, operator="eq")]
cof_warp_not_blue_filter = [OptionFilter(WarpCoF, (0, 2), operator="in")]
cof_warp_blue_filter = [OptionFilter(WarpCoF, (1, 3), operator="in")]
cof_warp_not_red_filter = [OptionFilter(WarpCoF, (0, 1), operator="in")]
cof_warp_red_filter = [OptionFilter(WarpCoF, (2, 3), operator="in")]
cof_warp_either_filter = [OptionFilter(WarpCoF, 0, operator="ne")]
cof_warp_neither_filter = [OptionFilter(WarpCoF, 0, operator="eq")]
cof_warp_both_filter = [OptionFilter(WarpCoF, 3, operator="eq")]
fow_warp_not_blue_filter = [OptionFilter(WarpFoW, (0, 2), operator="in")]
fow_warp_blue_filter = [OptionFilter(WarpFoW, (1, 3), operator="in")]
fow_warp_not_red_filter = [OptionFilter(WarpFoW, (0, 1), operator="in")]
fow_warp_red_filter = [OptionFilter(WarpFoW, (2, 3), operator="in")]
fow_warp_either_filter = [OptionFilter(WarpFoW, 0, operator="ne")]
fow_warp_neither_filter = [OptionFilter(WarpFoW, 0, operator="eq")]
fow_warp_both_filter = [OptionFilter(WarpFoW, 3, operator="eq")]
tod_warp_not_blue_filter = [OptionFilter(WarpToD, (0, 2), operator="in")]
tod_warp_blue_filter = [OptionFilter(WarpToD, (1, 3), operator="in")]
tod_warp_not_red_filter = [OptionFilter(WarpToD, (0, 1), operator="in")]
tod_warp_red_filter = [OptionFilter(WarpToD, (2, 3), operator="in")]
tod_warp_either_filter = [OptionFilter(WarpToD, 0, operator="ne")]
tod_warp_neither_filter = [OptionFilter(WarpToD, 0, operator="eq")]
tod_warp_both_filter = [OptionFilter(WarpToD, 3, operator="eq")]
pow_warp_not_blue_filter = [OptionFilter(WarpPoW, (0, 2), operator="in")]
pow_warp_blue_filter = [OptionFilter(WarpPoW, (1, 3), operator="in")]
pow_warp_not_red_filter = [OptionFilter(WarpPoW, (0, 1), operator="in")]
pow_warp_red_filter = [OptionFilter(WarpPoW, (2, 3), operator="in")]
pow_warp_either_filter = [OptionFilter(WarpPoW, 0, operator="ne")]
pow_warp_neither_filter = [OptionFilter(WarpPoW, 0, operator="eq")]
pow_warp_both_filter = [OptionFilter(WarpPoW, 3, operator="eq")]
dhc_warp_not_blue_filter = [OptionFilter(WarpDHC, (0, 2), operator="in")]
dhc_warp_blue_filter = [OptionFilter(WarpDHC, (1, 3), operator="in")]
dhc_warp_not_red_filter = [OptionFilter(WarpDHC, (0, 1), operator="in")]
dhc_warp_red_filter = [OptionFilter(WarpDHC, (2, 3), operator="in")]
dhc_warp_either_filter = [OptionFilter(WarpDHC, 0, operator="ne")]
dhc_warp_neither_filter = [OptionFilter(WarpDHC, 0, operator="eq")]
dhc_warp_both_filter = [OptionFilter(WarpDHC, 3, operator="eq")]


dws_one_key_rule = Has(TMCItem.SMALL_KEY_DWS, count=FromMultiplierResolver(1, DWSKeyMultiplier))
dws_two_key_rule = Has(TMCItem.SMALL_KEY_DWS, count=FromMultiplierResolver(2, DWSKeyMultiplier))
dws_three_key_rule = Has(TMCItem.SMALL_KEY_DWS, count=FromMultiplierResolver(3, DWSKeyMultiplier))
dws_four_key_rule = Has(TMCItem.SMALL_KEY_DWS, count=FromMultiplierResolver(4, DWSKeyMultiplier))

cof_one_key_rule = Has(TMCItem.SMALL_KEY_COF, count=FromMultiplierResolver(1, CoFKeyMultiplier))
cof_two_key_rule = Has(TMCItem.SMALL_KEY_COF, count=FromMultiplierResolver(2, CoFKeyMultiplier))

fow_one_key_rule = Has(TMCItem.SMALL_KEY_COF, count=FromMultiplierResolver(1, FoWKeyMultiplier))
fow_two_key_rule = Has(TMCItem.SMALL_KEY_COF, count=FromMultiplierResolver(2, FoWKeyMultiplier))
fow_three_key_rule = Has(TMCItem.SMALL_KEY_COF, count=FromMultiplierResolver(3, FoWKeyMultiplier))
fow_four_key_rule = Has(TMCItem.SMALL_KEY_COF, count=FromMultiplierResolver(4, FoWKeyMultiplier))

tod_one_key_rule = Has(TMCItem.SMALL_KEY_TOD, count=FromMultiplierResolver(1, ToDKeyMultiplier))
tod_two_key_rule = Has(TMCItem.SMALL_KEY_TOD, count=FromMultiplierResolver(2, ToDKeyMultiplier))
tod_three_key_rule = Has(TMCItem.SMALL_KEY_TOD, count=FromMultiplierResolver(3, ToDKeyMultiplier))
tod_four_key_rule = Has(TMCItem.SMALL_KEY_TOD, count=FromMultiplierResolver(4, ToDKeyMultiplier))

rc_one_key_rule = Has(TMCItem.SMALL_KEY_RC, count=FromMultiplierResolver(1, RCKeyMultiplier))
rc_two_key_rule = Has(TMCItem.SMALL_KEY_RC, count=FromMultiplierResolver(2, RCKeyMultiplier))
rc_three_key_rule = Has(TMCItem.SMALL_KEY_RC, count=FromMultiplierResolver(3, RCKeyMultiplier))

pow_one_key_rule = Has(TMCItem.SMALL_KEY_POW, count=FromMultiplierResolver(1, PoWKeyMultiplier))
pow_two_key_rule = Has(TMCItem.SMALL_KEY_POW, count=FromMultiplierResolver(2, PoWKeyMultiplier))
pow_three_key_rule = Has(TMCItem.SMALL_KEY_POW, count=FromMultiplierResolver(3, PoWKeyMultiplier))
pow_four_key_rule = Has(TMCItem.SMALL_KEY_POW, count=FromMultiplierResolver(4, PoWKeyMultiplier))
pow_five_key_rule = Has(TMCItem.SMALL_KEY_POW, count=FromMultiplierResolver(5, PoWKeyMultiplier))
pow_six_key_rule = Has(TMCItem.SMALL_KEY_POW, count=FromMultiplierResolver(6, PoWKeyMultiplier))

dhc_one_key_rule = Has(TMCItem.SMALL_KEY_DHC, count=FromMultiplierResolver(1, DHCKeyMultiplier))
dhc_two_key_rule = Has(TMCItem.SMALL_KEY_DHC, count=FromMultiplierResolver(2, DHCKeyMultiplier))
dhc_three_key_rule = Has(TMCItem.SMALL_KEY_DHC, count=FromMultiplierResolver(3, DHCKeyMultiplier))
dhc_four_key_rule = Has(TMCItem.SMALL_KEY_DHC, count=FromMultiplierResolver(4, DHCKeyMultiplier))
dhc_five_key_rule = Has(TMCItem.SMALL_KEY_DHC, count=FromMultiplierResolver(5, DHCKeyMultiplier))


bomb_dust_filter = [OptionFilter(Tricks, TMCTricks.BOMB_DUST, operator="contains")]
mushroom_filter = [OptionFilter(Tricks, TMCTricks.MUSHROOM, operator="contains")]
arrow_break_filter = [OptionFilter(Tricks, TMCTricks.ARROWS_BREAK, operator="contains")]
bobomb_walls_filter = [OptionFilter(Tricks, TMCTricks.BOBOMB_WALLS, operator="contains")]
likelike_swordless_filter = [OptionFilter(Tricks, TMCTricks.LIKELIKE_SWORDLESS, operator="contains")]
boots_guards_filter = [OptionFilter(Tricks, TMCTricks.BOOTS_GUARDS, operator="contains")]
beam_crenel_switch_filter = [OptionFilter(Tricks, TMCTricks.BEAM_CRENEL_SWITCH, operator="contains")]
downthrust_beetle_filter = [OptionFilter(Tricks, TMCTricks.DOWNTHRUST_BEETLE, operator="contains")]
dark_rooms_filter = [OptionFilter(Tricks, TMCTricks.DARK_ROOMS, operator="contains")]
cape_extensions_filter = [OptionFilter(Tricks, TMCTricks.CAPE_EXTENSIONS, operator="contains")]
lake_minish_filter = [OptionFilter(Tricks, TMCTricks.LAKE_MINISH, operator="contains")]
cabin_swim_filter = [OptionFilter(Tricks, TMCTricks.CABIN_SWIM, operator="contains")]
sharks_swordless_filter = [OptionFilter(Tricks, TMCTricks.SHARKS_SWORDLESS, operator="contains")]
pow_cane_filter = [OptionFilter(Tricks, TMCTricks.POW_NOCANE, operator="contains")]
pot_puzzle_filter = [OptionFilter(Tricks, TMCTricks.POT_PUZZLE, operator="contains")]
fow_pot_filter = [OptionFilter(Tricks, TMCTricks.FOW_POT, operator="contains")]
dhc_cannon_filter = [OptionFilter(Tricks, TMCTricks.DHC_CANNONS, operator="contains")]
dhc_clone_filter = [OptionFilter(Tricks, TMCTricks.DHC_CLONES, operator="contains")]
dhc_spin_filter = [OptionFilter(Tricks, TMCTricks.DHC_SPIN, operator="contains")]


has_sword = HasAny(
    TMCItem.SMITHS_SWORD,
    TMCItem.WHITE_SWORD_GREEN,
    TMCItem.WHITE_SWORD_RED,
    TMCItem.WHITE_SWORD_BLUE,
    TMCItem.FOUR_SWORD,
    TMCItem.PROGRESSIVE_SWORD,
)
has_shield = HasAny(TMCItem.PROGRESSIVE_SHIELD, TMCItem.SHIELD, TMCItem.MIRROR_SHIELD)
has_mirror_shield = Has(TMCItem.PROGRESSIVE_SHIELD, 2) | Has(TMCItem.MIRROR_SHIELD)
has_bow = HasAny(TMCItem.BOW, TMCItem.LIGHT_ARROW, TMCItem.PROGRESSIVE_BOW)
has_lightarrows = Has(TMCItem.LIGHT_ARROW) | Has(TMCItem.PROGRESSIVE_BOW, 2)
has_boomerang = HasAny(TMCItem.BOOMERANG, TMCItem.MAGIC_BOOMERANG, TMCItem.PROGRESSIVE_BOOMERANG)
has_magic_boomerang = Has(TMCItem.MAGIC_BOOMERANG) | Has(TMCItem.PROGRESSIVE_BOOMERANG, 2)
has_bow_weapon = has_bow | [OptionFilter(WeaponBow, 1)]
has_bomb_weapon = Has(TMCItem.BOMB_BAG) | [OptionFilter(WeaponBomb, 0, operator="gt")]
has_bomb_weapon_boss = Has(TMCItem.BOMB_BAG, 2) | [OptionFilter(WeaponBomb, 2)]
has_gust_weapon = Has(TMCItem.GUST_JAR) | [OptionFilter(WeaponGust, 1)]
has_lantern_weapon = Has(TMCItem.LANTERN) | [OptionFilter(WeaponLantern, 1)]
has_weapon = has_sword | has_bow_weapon | has_bomb_weapon
has_weapon_boss = has_sword | has_bomb_weapon
has_weapon_helm_ghini = has_sword | has_bow_weapon | has_gust_weapon
has_weapon_gleerok_mazaal = has_sword | has_bomb_weapon | has_bow_weapon  # This is the same as `has_weapon_boss`?
has_weapon_wizzrobe = has_sword | has_bomb_weapon | has_bow_weapon | has_lantern_weapon
has_weapon_scissor = has_sword | has_bomb_weapon_boss

can_spin = has_sword & HasAny(TMCItem.PROGRESSIVE_SCROLL, TMCItem.SPIN_ATTACK)
can_beam = has_sword & HasAny(TMCItem.SWORD_BEAM, TMCItem.PERIL_BEAM)
can_hit_distance = has_boomerang | Has(TMCItem.BOMB_BAG) | has_bow | can_beam


crenel_crest = Has(TMCItem.OCARINA, options=[OptionFilter(WindCrestCrenel, 1)])
falls_crest = Has(TMCItem.OCARINA, options=[OptionFilter(WindCrestFalls, 1)])
clouds_crest = Has(TMCItem.OCARINA, options=[OptionFilter(WindCrestClouds, 1)])
swamp_crest = Has(TMCItem.OCARINA, options=[OptionFilter(WindCrestSwamp, 1)])
smith_crest = Has(TMCItem.OCARINA, options=[OptionFilter(WindCrestSmith, 1)])
minish_crest = Has(TMCItem.OCARINA, options=[OptionFilter(WindCrestMinish, 1)])


blow_dust = (Has(TMCItem.BOMB_BAG) | bomb_dust_filter) | Has(TMCItem.GUST_JAR)
mushroom = (Has(TMCItem.GUST_JAR) | mushroom_filter) | HasAny(TMCItem.BOMB_BAG, TMCItem.GRIP_RING)
arrow_break = has_lightarrows | arrow_break_filter
likelike = (has_weapon | likelike_swordless_filter) | Has(TMCItem.MOLE_MITTS)
dark_room = (True_() | dark_rooms_filter) | Has(TMCItem.LANTERN)
cape_extend = (Has(TMCItem.ROCS_CAPE) | cape_extensions_filter) | Has(TMCItem.FLIPPERS)
lake_minish = (HasAll(TMCItem.OCARINA, TMCItem.FLIPPERS) | lake_minish_filter) | Has(TMCItem.PEGASUS_BOOTS)
cabin_swim = (Has(TMCItem.FLIPPERS) | cabin_swim_filter) | Has(TMCItem.GUST_JAR)
shark_kill = (True_() | sharks_swordless_filter) | has_weapon
fow_pot = Has(TMCItem.GUST_JAR) | fow_pot_filter
pow_jump = (Has(TMCItem.ROCS_CAPE) | pow_cane_filter) | (HasAll(TMCItem.CANE_OF_PACCI, TMCItem.ROCS_CAPE) & CanSplit(3))
pow_pot = ((HasAll(TMCItem.ROCS_CAPE, TMCEvent.POW_1ST_HALF_3F_ITEM_DROP)) | pot_puzzle_filter) | CanSplit(
    3, allow_max=True
) & Has(TMCItem.POWER_BRACELETS) & can_hit_distance
dhc_cannons = ((has_sword & Has(TMCItem.BOMB_BAG)) | dhc_cannon_filter) | CanSplit(4)
dhc_pads = (CanSplit(2, allow_max=True) | dhc_clone_filter) | CanSplit(4)
dhc_spin = (can_spin | dhc_spin_filter) | CanSplit(4)

downthrust = has_sword & HasAll(TMCItem.ROCS_CAPE, TMCItem.DOWNTHRUST)
can_pass_trees = (  # The small trees such as in North/South Hyrule Field
    HasAny(TMCItem.BOMB_BAG, TMCItem.LANTERN) | has_sword | arrow_break
)
access_town_left = HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS, TMCItem.CANE_OF_PACCI)
has_bottle = HasGroup("Bottle")
access_town_fountain = access_town_left & has_bottle
complete_book_quest = HasAll(
    TMCItem.OCARINA, TMCItem.CANE_OF_PACCI, TMCItem.RED_BOOK, TMCItem.BLUE_BOOK, TMCItem.GREEN_BOOK
)
access_lonlon_right = (  # Assumes can_pass_trees is already used somewhere in the chain
    HasAny(TMCItem.LONLON_KEY, TMCItem.ROCS_CAPE, TMCItem.OCARINA) | HasAll(TMCItem.FLIPPERS, TMCItem.MOLE_MITTS)
)
access_minish_woods_top_left = HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE) | (
    access_lonlon_right & Has(TMCItem.CANE_OF_PACCI)
)

dws_blue_warp = True_(options=dws_warp_blue_filter)
dws_red_warp = True_(options=dws_warp_red_filter)
dws_1st_door = Has(TMCItem.SMALL_KEY_DWS, count=FromMultiplierResolver(4, DWSKeyMultiplier))
dws_2nd_half = Or(dws_two_key_rule, Has(TMCItem.GUST_JAR), options=dws_warp_not_blue_filter)
cof_blue_warp = True_(options=cof_warp_blue_filter)
cof_red_warp = True_(options=cof_warp_red_filter)
fow_blue_warp = has_weapon_boss & fow_warp_blue_filter
fow_red_warp = True_(options=fow_warp_red_filter)
tod_blue_warp = has_weapon_scissor & tod_warp_blue_filter
tod_red_warp = And(HasAll(TMCItem.BOMB_BAG, TMCItem.LANTERN), has_weapon_boss, options=tod_warp_red_filter)
tod_right_ice = HasAny(TMCEvent.DROPLETS_EAST_SWITCH, TMCItem.LANTERN)
pow_blue_warp = has_weapon_boss & pow_warp_blue_filter
pow_red_warp = True_(options=pow_warp_red_filter)
pow_1st_door = (pow_four_key_rule & pow_warp_either_filter) | (pow_one_key_rule & pow_warp_neither_filter)
pow_2nd_door = pow_six_key_rule & pow_warp_red_filter
pow_red_chest = can_hit_distance & (Has(TMCItem.ROCS_CAPE, options=pow_warp_red_filter, filtered_resolution=True))
pow_red_warp_door = pow_five_key_rule
pow_last_door = pow_six_key_rule
dhc_blue_warp = has_weapon_boss & dhc_warp_blue_filter
dhc_red_warp = has_weapon & dhc_warp_red_filter
dhc_door = (dhc_five_key_rule & dhc_warp_either_filter) | (dhc_one_key_rule & dhc_warp_neither_filter)
dhc_switch_gap = has_bow | has_boomerang | can_beam
dhc_south_towers = dhc_warp_either_filter | HasAny(TMCItem.BOMB_BAG, TMCItem.ROCS_CAPE)


def set_rules(world: MinishCapWorld) -> None:
    world.set_completion_rule(Has("Victory"))
    connect_regions(world)
    set_location_rules(world)


def connect_regions(world: MinishCapWorld):
    region_map = get_region_map(world)

    _ = [
        world.create_entrance(region_map[from_region], region_map[to_region], rule)
        for from_region, connections in REGION_RULES.items()
        for to_region, rule in connections.items()
    ]
    pass


def set_location_rules(world: MinishCapWorld):
    location_map = get_location_map(world)

    _ = [
        world.set_rule(location_map[location], rule)
        for location, rule in LOCATION_RULES.items()
        if rule is not None and location in location_map
    ]


REGION_RULES: dict[TMCRegion, dict[TMCRegion, Rule[Any] | None]] = {
    TMCRegion.SOUTH_FIELD: {
        TMCRegion.HYRULE_TOWN: None,
        TMCRegion.EASTERN_HILLS: smith_crest,
        TMCRegion.SOUTH_PUDDLE: can_pass_trees | HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS),
        TMCRegion.LAKE_HYLIA_NORTH: Has(TMCItem.OCARINA),
        TMCRegion.BELARI: minish_crest,
        TMCRegion.CASTOR_WILDS: swamp_crest,
        TMCRegion.WIND_TRIBE: clouds_crest,
        TMCRegion.UPPER_FALLS: falls_crest,
        TMCRegion.MELARI: crenel_crest,
    },
    TMCRegion.SOUTH_PUDDLE: {
        TMCRegion.SOUTH_FIELD: can_pass_trees | HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS),
    },
    TMCRegion.HYRULE_TOWN: {
        TMCRegion.NORTH_FIELD: None,
        TMCRegion.SOUTH_FIELD: None,  # redundant
        TMCRegion.LONLON: Has(TMCItem.BOMB_BAG),
        TMCRegion.TRILBY_HIGHLANDS: can_spin | (Has(TMCItem.PEGASUS_BOOTS, options=boots_guards_filter)),
    },
    TMCRegion.NORTH_FIELD: {
        TMCRegion.CASTLE_EXTERIOR: None,
        TMCRegion.HYRULE_TOWN: None,  # redundant
        TMCRegion.LONLON: can_pass_trees,
        TMCRegion.TRILBY_HIGHLANDS: HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE),
        TMCRegion.FALLS_ENTRANCE: Has(TMCItem.BOMB_BAG),
        TMCRegion.ROYAL_VALLEY: CanSplit(3, True) & (cape_extend | Has(TMCItem.BOMB_BAG)),
    },
    TMCRegion.CASTLE_EXTERIOR: {
        TMCRegion.NORTH_FIELD: None,  # redundant
        TMCRegion.SANCTUARY: None,
    },
    TMCRegion.SANCTUARY: {
        TMCRegion.CASTLE_EXTERIOR: None,
        TMCRegion.STAINED_GLASS: CanActivatePedestal(),
    },
    TMCRegion.LONLON: {
        TMCRegion.HYRULE_TOWN: Has(TMCItem.BOMB_BAG),  # redundant
        TMCRegion.NORTH_FIELD: can_pass_trees,  # redundant
        TMCRegion.EASTERN_HILLS: Has(TMCItem.BOMB_BAG),
        TMCRegion.MINISH_WOODS: None,  # Doesn't directly connect, but nothing is in between
        TMCRegion.LOWER_FALLS: Has(TMCItem.CANE_OF_PACCI),
        TMCRegion.LAKE_HYLIA_NORTH: Has(TMCItem.LONLON_KEY),
    },
    TMCRegion.EASTERN_HILLS: {
        TMCRegion.LONLON: Has(TMCItem.BOMB_BAG),
        TMCRegion.BELARI: Has(TMCItem.BOMB_BAG),
        TMCRegion.SOUTH_FIELD: can_pass_trees,
    },
    TMCRegion.LAKE_HYLIA_NORTH: {
        TMCRegion.LONLON: None,
        # allows Ocarina warp access to lonlon and minish woods
        TMCRegion.LAKE_HYLIA_SOUTH: cape_extend,
        TMCRegion.DUNGEON_TOD_ENTRANCE: cape_extend,
        # TMCRegion.MINISH_WOODS: # Already connected
    },
    TMCRegion.MINISH_WOODS: {
        TMCRegion.LONLON: None,
        TMCRegion.LAKE_HYLIA_SOUTH: access_minish_woods_top_left & Has(TMCItem.MOLE_MITTS),
        TMCRegion.LAKE_HYLIA_NORTH: Has(TMCItem.ROCS_CAPE),
        TMCRegion.DUNGEON_DWS_ENTRANCE: HasAny(TMCItem.FLIPPERS, TMCItem.JABBER_NUT),
        TMCRegion.BELARI: HasAny(TMCItem.BOMB_BAG, TMCEvent.CLEAR_DWS),
    },
    TMCRegion.BELARI: {
        TMCRegion.MINISH_WOODS: None,
        TMCRegion.EASTERN_HILLS: Has(TMCItem.BOMB_BAG),
    },
    TMCRegion.WESTERN_WOODS: {
        TMCRegion.SOUTH_PUDDLE: None,
        TMCRegion.CASTOR_WILDS: HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE),
        TMCRegion.TRILBY_HIGHLANDS: None,
    },
    TMCRegion.TRILBY_HIGHLANDS: {
        TMCRegion.HYRULE_TOWN: None,  # redundant
        TMCRegion.NORTH_FIELD:  # redundant
        HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS) | (Has(TMCItem.CANE_OF_PACCI) & has_sword),
        TMCRegion.WESTERN_WOODS: CanSplit(2, True),
        TMCRegion.CRENEL_BASE: has_bottle,
    },
    TMCRegion.CRENEL_BASE: {
        TMCRegion.TRILBY_HIGHLANDS: None,
        TMCRegion.CRENEL: Has(TMCItem.GRIP_RING) | (Has(TMCItem.BOMB_BAG) & blow_dust & has_bottle),
    },
    TMCRegion.CRENEL: {
        TMCRegion.CRENEL_BASE: Has(TMCItem.GRIP_RING),
        TMCRegion.MELARI: (mushroom & Has(TMCItem.CANE_OF_PACCI))
        | (
            Has(TMCItem.GRIP_RING)
            & (HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE) | arrow_break)
            & (has_bow | has_boomerang | Has(TMCItem.BOMB_BAG) | (Has(TMCItem.ROCS_CAPE) | can_beam))
        ),
    },
    TMCRegion.MELARI: {
        TMCRegion.CRENEL: None,
        TMCRegion.DUNGEON_COF_ENTRANCE: None,
    },
    TMCRegion.CASTOR_WILDS: {
        TMCRegion.WESTERN_WOODS: HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE) | has_bow,
        TMCRegion.WIND_RUINS: Has(TMCItem.KINSTONE_GOLD_SWAMP, 3)
        & (Has(TMCItem.ROCS_CAPE) | (Has(TMCItem.PEGASUS_BOOTS) & (swamp_crest | has_bow | Has(TMCItem.FLIPPERS)))),
    },
    TMCRegion.WIND_RUINS: {
        TMCRegion.DUNGEON_FOW_ENTRANCE: has_sword & has_weapon,  # redundancy for later logic improvements
    },
    TMCRegion.ROYAL_VALLEY: {
        TMCRegion.NORTH_FIELD: None,  # redundant
        TMCRegion.TRILBY_HIGHLANDS: None,  # redundant
        TMCRegion.GRAVEYARD: HasAll(TMCItem.GRAVEYARD_KEY, TMCItem.PEGASUS_BOOTS) & dark_room,
    },
    TMCRegion.GRAVEYARD: {
        TMCRegion.DUNGEON_RC: CanSplit(3),
    },
    TMCRegion.DUNGEON_RC: {
        TMCRegion.DUNGEON_RC_CLEAR: has_weapon & Has(TMCItem.SMALL_KEY_RC, 3) & Has(TMCItem.LANTERN),
    },
    TMCRegion.FALLS_ENTRANCE: {
        TMCRegion.MIDDLE_FALLS: Has(TMCItem.KINSTONE_GOLD_FALLS) & dark_room,
    },
    TMCRegion.MIDDLE_FALLS: {
        TMCRegion.FALLS_ENTRANCE: Has(TMCItem.FLIPPERS),
        TMCRegion.UPPER_FALLS: Has(TMCItem.GRIP_RING),
    },
    TMCRegion.UPPER_FALLS: {
        TMCRegion.MIDDLE_FALLS: Has(TMCItem.GRIP_RING),
        TMCRegion.CLOUDS: Has(TMCItem.GRIP_RING),
    },
    TMCRegion.CLOUDS: {
        TMCRegion.UPPER_FALLS: Has(TMCItem.GRIP_RING),
        TMCRegion.WIND_TRIBE: Has(TMCItem.KINSTONE_GOLD_CLOUD, 5) & HasAny(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    },
    TMCRegion.WIND_TRIBE: {
        TMCRegion.CLOUDS: None,
        TMCRegion.DUNGEON_POW_ENTRANCE: None,
    },
    TMCRegion.CASTLE_EXTERIOR: {
        TMCRegion.DUNGEON_DHC_ENTRANCE: True_(options=[OptionFilter(DHCAccess, DHCAccess.option_open)])
    },
    # region DWS
    TMCRegion.DUNGEON_DWS_ENTRANCE: {
        TMCRegion.DUNGEON_DWS_BARREL: dws_1st_door,
        TMCRegion.DUNGEON_DWS_BLUE_WARP: dws_blue_warp,
    },
    TMCRegion.DUNGEON_DWS_BLUE_WARP: {
        TMCRegion.DUNGEON_DWS_BACK_HALF: None,
    },
    TMCRegion.DUNGEON_DWS_ENTRANCE: {
        TMCRegion.DUNGEON_DWS_RED_WARP: dws_red_warp,
    },
    TMCRegion.DUNGEON_DWS_BARREL: {
        TMCRegion.DUNGEON_DWS_MULLDOZER: Has(TMCItem.SMALL_KEY_DWS, 4),
        TMCRegion.DUNGEON_DWS_BACK_HALF: dws_2nd_half,
        TMCRegion.DUNGEON_DWS_RED_WARP: Has(TMCItem.SMALL_KEY_DWS, 4) & Has(TMCItem.GUST_JAR),
    },
    TMCRegion.DUNGEON_DWS_BACK_HALF: {
        TMCRegion.DUNGEON_DWS_BLUE_WARP: blow_dust,
        TMCRegion.DUNGEON_DWS_BARREL: None,
    },
    TMCRegion.DUNGEON_DWS_MULLDOZER: {
        TMCRegion.DUNGEON_DWS_BACK_HALF: None,
    },
    TMCRegion.DUNGEON_DWS_ENTRANCE: {
        TMCRegion.DUNGEON_DWS_CLEAR: HasAll(TMCItem.BIG_KEY_DWS, TMCItem.GUST_JAR) & has_weapon_boss,
    },
    # endregion
    # region CoF
    TMCRegion.DUNGEON_COF_ENTRANCE: {
        TMCRegion.DUNGEON_COF_MAIN: (
            Has(TMCItem.BOMB_BAG) | ((has_sword | Has(TMCItem.GUST_JAR)) & bobomb_walls_filter)
        )
        & has_weapon  # Spike Beetle Fight
        & (
            has_shield
            | HasAny(TMCItem.CANE_OF_PACCI, TMCItem.BOMB_BAG)
            | (downthrust & downthrust_beetle_filter)  # TODO: Double-check correct usage of optionfilter merging
        )
    },
    TMCRegion.DUNGEON_COF_MAIN: {
        TMCRegion.DUNGEON_COF_MINECART: (
            (Has(TMCItem.SMALL_KEY_COF, 2) & dws_warp_blue_filter)
            | (Has(TMCItem.SMALL_KEY_COF, 1) & dws_warp_not_blue_filter)
        )
        & has_sword
    },
    TMCRegion.DUNGEON_COF_MINECART: {
        TMCRegion.DUNGEON_COF_BLUE_WARP: has_weapon & HasAny(TMCItem.CANE_OF_PACCI, TMCItem.ROCS_CAPE),
    },
    TMCRegion.DUNGEON_COF_ENTRANCE: {
        TMCRegion.DUNGEON_COF_BLUE_WARP: cof_blue_warp,
    },
    TMCRegion.DUNGEON_COF_BLUE_WARP: {
        TMCRegion.DUNGEON_COF_MINECART: Has(TMCItem.CANE_OF_PACCI),
        TMCRegion.DUNGEON_COF_LAVA_BASEMENT: has_sword & Has(TMCItem.SMALL_KEY_COF, 2) & Has(TMCItem.CANE_OF_PACCI),
    },
    TMCRegion.DUNGEON_COF_ENTRANCE: {
        TMCRegion.DUNGEON_COF_LAVA_BASEMENT: cof_red_warp,
    },
    TMCRegion.DUNGEON_COF_LAVA_BASEMENT: {
        TMCRegion.DUNGEON_COF_CLEAR: has_sword
        & has_weapon_gleerok_mazaal
        & HasAll(TMCItem.CANE_OF_PACCI, TMCItem.BIG_KEY_COF),
    },
    # endregion
    # region FoW
    TMCRegion.DUNGEON_FOW_ENTRANCE: {
        TMCRegion.DUNGEON_FOW_EYEGORE: has_bow,
        TMCRegion.DUNGEON_FOW_BLUE_WARP: fow_blue_warp,
        TMCRegion.DUNGEON_FOW_CLEAR: And(
            HasAll(TMCItem.MOLE_MITTS, TMCItem.BIG_KEY_FOW), has_bow, has_weapon_gleerok_mazaal
        ),
    },
    TMCRegion.DUNGEON_FOW_EYEGORE: {
        TMCRegion.DUNGEON_FOW_BLUE_WARP: fow_four_key_rule,
    },
    TMCRegion.DUNGEON_FOW_BLUE_WARP: {
        TMCRegion.DUNGEON_FOW_EYEGORE: None,
    },
    # endregion
    # region ToD
    TMCRegion.DUNGEON_TOD_ENTRANCE: {
        TMCRegion.DUNGEON_TOD_LEFT_BASEMENT: tod_blue_warp,
        TMCRegion.DUNGEON_TOD_WEST_SWITCH_LEDGE: tod_red_warp,
        TMCRegion.DUNGEON_TOD_MAIN: Has(TMCItem.BIG_KEY_TOD),
    },
    TMCRegion.DUNGEON_TOD_WEST_SWITCH_LEDGE: {
        TMCRegion.DUNGEON_TOD_MAIN: None,
        TMCRegion.DUNGEON_TOD_WEST_SWITCH: CanSplit(2),
    },
    TMCRegion.DUNGEON_TOD_LEFT_BASEMENT: {
        TMCRegion.DUNGEON_TOD_MAIN: None,
        TMCRegion.DUNGEON_TOD_DARK_MAZE_END: Has(TMCItem.ROCS_CAPE),
        TMCRegion.DUNGEON_TOD_EAST_SWITCH: CanSplit(2),
    },
    TMCRegion.DUNGEON_TOD_MAIN: {
        TMCRegion.DUNGEON_TOD_LEFT_BASEMENT: And(tod_four_key_rule, HasAll(TMCItem.FLIPPERS, TMCItem.GUST_JAR)),
        TMCRegion.DUNGEON_TOD_DARK_MAZE_END: And(Has(TMCItem.LANTERN), has_weapon_scissor, tod_four_key_rule),
        TMCRegion.DUNGEON_TOD_CLEAR: And(
            Or(has_shield, has_sword),
            HasAll(TMCEvent.DROPLETS_WEST_SWITCH, TMCEvent.DROPLETS_EAST_SWITCH, TMCItem.LANTERN),
        ),
    },
    TMCRegion.DUNGEON_TOD_DARK_MAZE_END: {
        TMCRegion.DUNGEON_TOD_LEFT_BASEMENT: Has(TMCItem.ROCS_CAPE),
        TMCRegion.DUNGEON_TOD_WEST_SWITCH_LEDGE: And(
            CanSplit(2), HasAll(TMCItem.LANTERN, TMCItem.BOMB_BAG), cape_extend
        ),
    },
    # endregion
    # region PoW
    TMCRegion.DUNGEON_POW_ENTRANCE: {
        TMCRegion.DUNGEON_POW_BLUE_WARP: pow_blue_warp,
        TMCRegion.DUNGEON_POW_RED_WARP: pow_red_warp,
        TMCRegion.DUNGEON_POW_OUT_1F: And(
            CanSplit(3), Or(can_hit_distance, HasAny(TMCItem.ROCS_CAPE, TMCItem.GUST_JAR))
        ),
    },
    TMCRegion.DUNGEON_POW_OUT_1F: {
        TMCRegion.DUNGEON_POW_OUT_2F: pow_jump,
    },
    TMCRegion.DUNGEON_POW_OUT_2F: {
        TMCRegion.DUNGEON_POW_OUT_3F: And(CanSplit(3), Has(TMCItem.ROCS_CAPE)),
    },
    TMCRegion.DUNGEON_POW_OUT_3F: {
        TMCRegion.DUNGEON_POW_OUT_4F: And(pow_1st_door, Has(TMCItem.ROCS_CAPE)),
    },
    TMCRegion.DUNGEON_POW_OUT_4F: {TMCRegion.DUNGEON_POW_OUT_5F: Has(TMCItem.ROCS_CAPE)},
    TMCRegion.DUNGEON_POW_OUT_5F: {
        TMCRegion.DUNGEON_POW_BLUE_WARP: And(Has(TMCItem.BIG_KEY_POW), has_weapon_boss),
    },
    TMCRegion.DUNGEON_POW_BLUE_WARP: {
        TMCRegion.DUNGEON_POW_IN_1F: dark_room,
    },
    TMCRegion.DUNGEON_POW_IN_1F: {
        TMCRegion.DUNGEON_POW_IN_2F: None,
    },
    TMCRegion.DUNGEON_POW_IN_2F: {
        TMCRegion.DUNGEON_POW_IN_1F: dark_room,
        TMCRegion.DUNGEON_POW_IN_3F: And(pow_2nd_door, Has(TMCItem.ROCS_CAPE)),
    },
    TMCRegion.DUNGEON_POW_IN_3F: {
        TMCRegion.DUNGEON_POW_IN_2F: None,
        TMCRegion.DUNGEON_POW_IN_3F_SWITCH: And(
            has_sword, has_boomerang, has_bow, HasAny(TMCItem.GUST_JAR, TMCItem.BOMB_BAG)
        ),
        TMCRegion.DUNGEON_POW_IN_4F: has_weapon,
    },
    TMCRegion.DUNGEON_POW_IN_4F: {
        TMCRegion.DUNGEON_POW_IN_3F: None,
        TMCRegion.DUNGEON_POW_RED_WARP: And(Has(TMCItem.ROCS_CAPE), can_hit_distance),
    },
    TMCRegion.DUNGEON_POW_RED_WARP: {
        TMCRegion.DUNGEON_POW_IN_3F: Has(TMCItem.BOMB_BAG),
        TMCRegion.DUNGEON_POW_IN_4F: HasAll(TMCItem.BOMB_BAG, TMCItem.ROCS_CAPE),
        TMCRegion.DUNGEON_POW_IN_5F: And(pow_red_warp_door, Has(TMCItem.BOMB_BAG)),
    },
    TMCRegion.DUNGEON_POW_IN_5F: {
        TMCRegion.DUNGEON_POW_IN_3F: None,
        TMCRegion.DUNGEON_POW_IN_4F_END: pow_last_door,
    },
    TMCRegion.DUNGEON_POW_IN_4F_END: {
        TMCRegion.DUNGEON_POW_IN_5F_END: Has(TMCItem.ROCS_CAPE),
        TMCRegion.DUNGEON_POW_CLEAR: And(Has(TMCItem.ROCS_CAPE), Has(TMCItem.BIG_KEY_POW), CanSplit(3)),
    },
    # endregion
    # region Sanctuary
    TMCRegion.STAINED_GLASS: {
        TMCRegion.VAATI_FIGHT: And(
            HasAll(TMCItem.GUST_JAR, TMCItem.CANE_OF_PACCI),
            dark_room,
            has_bow,
            CanSplit(4),
            options=[OptionFilter(DHCAccess, DHCAccess.option_closed), OptionFilter(Goal, Goal.option_vaati)],
        ),
        TMCRegion.DUNGEON_DHC_B1_WEST: True_(options=[OptionFilter(DHCAccess, DHCAccess.option_closed, operator="ne")]),
    },
    # endregion
    # region DHC
    TMCRegion.DUNGEON_DHC_B1_WEST: {
        TMCRegion.SANCTUARY: None,  # Ped items
        TMCRegion.DUNGEON_DHC_B2: Has(TMCItem.BOMB_BAG),
        TMCRegion.DUNGEON_DHC_ENTRANCE: None,
    },
    TMCRegion.DUNGEON_DHC_B2: {
        TMCRegion.DUNGEON_DHC_B1_WEST: None,  # redundant
    },
    TMCRegion.DUNGEON_DHC_ENTRANCE: {
        TMCRegion.DUNGEON_DHC_B1_WEST: None,  # Ped items
        TMCRegion.CASTLE_EXTERIOR: None,  # redundant
        TMCRegion.DUNGEON_DHC_BLUE_WARP: dhc_blue_warp,
        TMCRegion.DUNGEON_DHC_RED_WARP: dhc_red_warp,
        TMCRegion.DUNGEON_DHC_B1_EAST: And(dhc_door, dhc_cannons, Has(TMCItem.BOMB_BAG)),
    },
    TMCRegion.DUNGEON_DHC_B1_EAST: {TMCRegion.DUNGEON_DHC_1F: has_weapon_boss},
    TMCRegion.DUNGEON_DHC_1F: {
        TMCRegion.DUNGEON_DHC_OUTSIDE: None,
    },
    TMCRegion.DUNGEON_DHC_OUTSIDE: {TMCRegion.DUNGEON_DHC_RED_WARP: And(CanSplit(4), dhc_switch_gap, has_weapon)},
    TMCRegion.DUNGEON_DHC_RED_WARP: {
        TMCRegion.DUNGEON_DHC_BLUE_WARP: And(
            Has(TMCItem.ROCS_CAPE), dhc_switch_gap, HasAny(TMCItem.BOMB_BAG, TMCItem.GUST_JAR), has_weapon_boss
        )
    },
    TMCRegion.DUNGEON_DHC_RED_WARP: {
        TMCRegion.VAATI_FIGHT: And(
            HasAll(TMCItem.BIG_KEY_DHC, TMCItem.GUST_JAR, TMCItem.CANE_OF_PACCI),
            has_weapon_boss,  # Darknut
            CanSplit(4),
            has_bow,
            dark_room,  # Don't make people do the final boss in the dark
        )
    },
    # endregion
}

LOCATION_RULES: dict[TMCLocation, Rule[Any] | None] = {
    # region South Field
    TMCLocation.SMITH_HOUSE_CHEST: None,
    TMCLocation.SMITH_HOUSE_SWORD: None,
    TMCLocation.SMITH_HOUSE_SHIELD: None,
    TMCLocation.SOUTH_FIELD_MINISH_SIZE_WATER_HOLE_HP: And(
        can_pass_trees, HasAll(TMCItem.PEGASUS_BOOTS, TMCItem.FLIPPERS)
    ),
    # All the following require Fusion 58
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM1: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM2: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM3: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM4: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM5: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM6: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM7: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM8: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM9: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM10: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM11: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM12: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM13: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM14: None,
    TMCLocation.SOUTH_FIELD_PUDDLE_FUSION_ITEM15: None,
    TMCLocation.SOUTH_FIELD_FUSION_CHEST: None,  # Fusion 53
    TMCLocation.SOUTH_FIELD_TREE_FUSION_HP: None,  # Fusion 32
    TMCLocation.SOUTH_FIELD_TINGLE_NPC: HasAll(TMCItem.CANE_OF_PACCI, TMCItem.TINGLE_TROPHY),
    # endregion
    # region Hyrule Town
    TMCLocation.TOWN_CAFE_LADY_NPC: None,
    TMCLocation.TOWN_SHOP_80_ITEM: CanPay(80),
    TMCLocation.TOWN_SHOP_300_ITEM: CanPay(300),
    TMCLocation.TOWN_SHOP_600_ITEM: CanPay(600),
    TMCLocation.TOWN_SHOP_EXTRA_600_ITEM: CanPay(600),
    TMCLocation.TOWN_SHOP_BEHIND_COUNTER_ITEM: access_town_left,
    TMCLocation.TOWN_SHOP_ATTIC_CHEST: access_town_left,
    TMCLocation.TOWN_BAKERY_ATTIC_CHEST: access_town_left,
    TMCLocation.TOWN_INN_BACKDOOR_HP: access_town_left,
    TMCLocation.TOWN_INN_LEDGE_CHEST: Has(TMCItem.LANTERN),
    TMCLocation.TOWN_INN_POT: None,
    TMCLocation.TOWN_WELL_RIGHT_CHEST: None,
    # Fusion 33
    TMCLocation.TOWN_GORON_MERCHANT_1_LEFT: CanPay(BoolMapperResolver(GoronJPPrices, 300, 200)),
    TMCLocation.TOWN_GORON_MERCHANT_1_MIDDLE: CanPay(BoolMapperResolver(GoronJPPrices, 200, 100)),
    TMCLocation.TOWN_GORON_MERCHANT_1_RIGHT: CanPay(50),
    # Fusion 33
    TMCLocation.TOWN_GORON_MERCHANT_2_LEFT: CanPay(300),
    TMCLocation.TOWN_GORON_MERCHANT_2_MIDDLE: CanPay(BoolMapperResolver(GoronJPPrices, 300, 200)),
    TMCLocation.TOWN_GORON_MERCHANT_2_RIGHT: CanPay(BoolMapperResolver(GoronJPPrices, 300, 200)),
    # Fusion 33
    TMCLocation.TOWN_GORON_MERCHANT_3_LEFT: CanPay(BoolMapperResolver(GoronJPPrices, 300, 400)),
    TMCLocation.TOWN_GORON_MERCHANT_3_MIDDLE: CanPay(300),
    TMCLocation.TOWN_GORON_MERCHANT_3_RIGHT: CanPay(300),
    # Fusion 33
    TMCLocation.TOWN_GORON_MERCHANT_4_LEFT: CanPay(BoolMapperResolver(GoronJPPrices, 300, 500)),
    TMCLocation.TOWN_GORON_MERCHANT_4_MIDDLE: CanPay(BoolMapperResolver(GoronJPPrices, 300, 400)),
    TMCLocation.TOWN_GORON_MERCHANT_4_RIGHT: CanPay(BoolMapperResolver(GoronJPPrices, 300, 400)),
    # Fusion 33
    TMCLocation.TOWN_GORON_MERCHANT_5_LEFT: CanPay(BoolMapperResolver(GoronJPPrices, 300, 600)),
    TMCLocation.TOWN_GORON_MERCHANT_5_MIDDLE: CanPay(BoolMapperResolver(GoronJPPrices, 300, 500)),
    TMCLocation.TOWN_GORON_MERCHANT_5_RIGHT: CanPay(BoolMapperResolver(GoronJPPrices, 300, 500)),
    TMCLocation.TOWN_DOJO_NPC_1: has_sword,
    TMCLocation.TOWN_DOJO_NPC_2: Or(Has(TMCItem.WHITE_SWORD_GREEN), Has(TMCItem.PROGRESSIVE_SWORD, 2)),
    TMCLocation.TOWN_DOJO_NPC_3: And(has_sword, Has(TMCItem.PEGASUS_BOOTS)),
    TMCLocation.TOWN_DOJO_NPC_4: And(has_sword, Has(TMCItem.ROCS_CAPE)),
    TMCLocation.TOWN_WELL_TOP_CHEST: Has(TMCItem.BOMB_BAG),
    TMCLocation.TOWN_SCHOOL_ROOF_CHEST: Has(TMCItem.CANE_OF_PACCI),
    TMCLocation.TOWN_SCHOOL_PATH_FUSION_CHEST: Has(TMCItem.CANE_OF_PACCI),  # Fusion 36
    TMCLocation.TOWN_SCHOOL_PATH_LEFT_CHEST: And(Has(TMCItem.CANE_OF_PACCI), CanSplit(4)),
    TMCLocation.TOWN_SCHOOL_PATH_MIDDLE_CHEST: And(Has(TMCItem.CANE_OF_PACCI), CanSplit(4)),
    TMCLocation.TOWN_SCHOOL_PATH_RIGHT_CHEST: And(Has(TMCItem.CANE_OF_PACCI), CanSplit(4)),
    TMCLocation.TOWN_SCHOOL_PATH_HP: And(Has(TMCItem.CANE_OF_PACCI), CanSplit(4)),
    TMCLocation.TOWN_DIGGING_LEFT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.TOWN_DIGGING_TOP_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.TOWN_DIGGING_RIGHT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.TOWN_WELL_LEFT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.TOWN_BELL_HP: Has(TMCItem.ROCS_CAPE),
    TMCLocation.TOWN_WATERFALL_FUSION_CHEST: Has(TMCItem.FLIPPERS),  # Fusion 42
    TMCLocation.TOWN_CARLOV_NPC: access_town_left,
    TMCLocation.TOWN_WELL_BOTTOM_CHEST: HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS),
    TMCLocation.TOWN_CUCCOS_LV_1_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_2_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_3_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_4_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_5_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_6_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_7_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_8_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_9_NPC: None,
    TMCLocation.TOWN_CUCCOS_LV_10_NPC: HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS),
    TMCLocation.TOWN_JULLIETA_ITEM: And(access_town_left, has_bottle),
    TMCLocation.TOWN_SIMULATION_CHEST: And(has_sword, CanPay(10)),
    TMCLocation.TOWN_SHOE_SHOP_NPC: Has(TMCItem.WAKEUP_MUSHROOM),
    TMCLocation.TOWN_MUSIC_HOUSE_LEFT_CHEST: Has(TMCItem.CARLOV_MEDAL),
    TMCLocation.TOWN_MUSIC_HOUSE_MIDDLE_CHEST: Has(TMCItem.CARLOV_MEDAL),
    TMCLocation.TOWN_MUSIC_HOUSE_RIGHT_CHEST: Has(TMCItem.CARLOV_MEDAL),
    TMCLocation.TOWN_MUSIC_HOUSE_HP: Has(TMCItem.CARLOV_MEDAL),
    TMCLocation.TOWN_WELL_PILLAR_CHEST: And(
        Has(TMCItem.MOLE_MITTS),
        HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS),
        CanSplit(3, True),
    ),
    TMCLocation.TOWN_DR_LEFT_ATTIC_ITEM: And(
        access_town_left,
        HasAll(TMCItem.POWER_BRACELETS, TMCItem.GUST_JAR),
        CanSplit(2),
    ),
    TMCLocation.TOWN_FOUNTAIN_BIG_CHEST: And(has_weapon, access_town_fountain, Has(TMCItem.CANE_OF_PACCI)),
    TMCLocation.TOWN_FOUNTAIN_SMALL_CHEST: And(access_town_fountain, HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE)),
    TMCLocation.TOWN_FOUNTAIN_HP: And(access_town_fountain, Has(TMCItem.ROCS_CAPE)),
    TMCLocation.TOWN_LIBRARY_YELLOW_MINISH_NPC: complete_book_quest,
    TMCLocation.TOWN_UNDER_LIBRARY_FROZEN_CHEST: HasAll(
        TMCItem.OCARINA, TMCItem.CANE_OF_PACCI, TMCItem.FLIPPERS, TMCItem.LANTERN
    ),
    TMCLocation.TOWN_UNDER_LIBRARY_BIG_CHEST: And(
        Or(
            And(complete_book_quest, Has(TMCItem.GRIP_RING), HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE)),
            HasAll(TMCItem.OCARINA, TMCItem.CANE_OF_PACCI, TMCItem.FLIPPERS),
        ),
        has_weapon_scissor,
    ),
    TMCLocation.TOWN_UNDER_LIBRARY_UNDERWATER: HasAll(TMCItem.OCARINA, TMCItem.CANE_OF_PACCI, TMCItem.FLIPPERS),
    # endregion
    # region North Field
    TMCLocation.NORTH_FIELD_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    TMCLocation.NORTH_FIELD_HP: Or(Has(TMCItem.BOMB_BAG), cape_extend),
    TMCLocation.NORTH_FIELD_TREE_FUSION_TOP_LEFT_CHEST: None,  # Fusion 59
    TMCLocation.NORTH_FIELD_TREE_FUSION_TOP_RIGHT_CHEST: None,  # Fusion 40
    TMCLocation.NORTH_FIELD_TREE_FUSION_BOTTOM_LEFT_CHEST: None,  # Fusion 4D
    TMCLocation.NORTH_FIELD_TREE_FUSION_BOTTOM_RIGHT_CHEST: None,  # Fusion 5A
    TMCLocation.NORTH_FIELD_TREE_FUSION_CENTER_BIG_CHEST: None,  # All of the above
    TMCLocation.NORTH_FIELD_WATERFALL_FUSION_DOJO_NPC:  # Fusion 15
    And(Has(TMCItem.FLIPPERS), has_sword),
    # endregion
    # region Castle Gardens
    TMCLocation.CASTLE_MOAT_LEFT_CHEST: Has(TMCItem.FLIPPERS),
    TMCLocation.CASTLE_MOAT_RIGHT_CHEST: Has(TMCItem.FLIPPERS),
    TMCLocation.CASTLE_GOLDEN_ROPE: has_sword,  # Fusion 3C
    TMCLocation.CASTLE_RIGHT_FOUNTAIN_FUSION_HP: None,  # Fusion 18
    TMCLocation.CASTLE_DOJO_HP: None,
    TMCLocation.CASTLE_DOJO_NPC: And(Has(TMCItem.LANTERN), has_sword),
    TMCLocation.CASTLE_RIGHT_FOUNTAIN_FUSION_MINISH_HOLE_CHEST: Has(TMCItem.PEGASUS_BOOTS),  # Fusion 18
    TMCLocation.CASTLE_LEFT_FOUNTAIN_FUSION_MINISH_HOLE_CHEST: Has(TMCItem.PEGASUS_BOOTS),  # Fusion 35
    # endregion
    # region Eastern Hills
    # Can Pass Trees
    TMCLocation.HILLS_GOLDEN_ROPE: has_sword,  # Fusion 55
    TMCLocation.HILLS_FUSION_CHEST: None,  # Fusion 16
    TMCLocation.HILLS_BEANSTALK_FUSION_LEFT_CHEST: None,  # Fusion 2E
    TMCLocation.HILLS_BEANSTALK_FUSION_HP: None,  # Fusion 2E
    TMCLocation.HILLS_BEANSTALK_FUSION_RIGHT_CHEST: None,  # Fusion 2E
    TMCLocation.HILLS_BOMB_CAVE_CHEST: Has(TMCItem.BOMB_BAG),
    TMCLocation.MINISH_GREAT_FAIRY_NPC: Has(TMCItem.CANE_OF_PACCI),
    TMCLocation.HILLS_FARM_DIG_CAVE_ITEM: Has(TMCItem.MOLE_MITTS),
    # endregion
    # region LonLon
    # Can Pass Trees
    TMCLocation.LON_LON_RANCH_POT: None,
    TMCLocation.LON_LON_PUDDLE_FUSION_BIG_CHEST: access_lonlon_right,  # Fusion 1E
    TMCLocation.LON_LON_CAVE_CHEST: And(access_lonlon_right, CanSplit(2, True)),
    TMCLocation.LON_LON_CAVE_SECRET_CHEST: And(
        access_lonlon_right, CanSplit(2, True), HasAll(TMCItem.BOMB_BAG, TMCItem.LANTERN)
    ),
    TMCLocation.LON_LON_PATH_FUSION_CHEST:  # Fusion 50
    And(access_lonlon_right, Has(TMCItem.PEGASUS_BOOTS)),
    TMCLocation.LON_LON_PATH_HP: And(access_lonlon_right, Has(TMCItem.PEGASUS_BOOTS)),
    TMCLocation.LON_LON_DIG_SPOT: And(
        access_lonlon_right, HasAny(TMCItem.CANE_OF_PACCI, TMCItem.ROCS_CAPE), Has(TMCItem.MOLE_MITTS)
    ),
    TMCLocation.LON_LON_NORTH_MINISH_CRACK_CHEST: And(
        access_lonlon_right, HasAny(TMCItem.CANE_OF_PACCI, TMCItem.ROCS_CAPE)
    ),
    TMCLocation.LON_LON_GORON_CAVE_FUSION_SMALL_CHEST: access_minish_woods_top_left,
    # 4 of Fusion 25, 26, 29, 2A, 2B, 2F
    TMCLocation.LON_LON_GORON_CAVE_FUSION_BIG_CHEST: access_minish_woods_top_left,
    # 6 of Fusion 25, 26, 29, 2A, 2B, 2F
    # endregion
    # region Lower Falls
    TMCLocation.FALLS_LOWER_LON_LON_FUSION_CHEST: None,  # Fusion 60
    TMCLocation.FALLS_LOWER_HP: None,
    TMCLocation.FALLS_LOWER_WATERFALL_FUSION_DOJO_NPC:  # Fusion 1D
    And(Has(TMCItem.FLIPPERS), has_sword),
    TMCLocation.FALLS_LOWER_ROCK_ITEM1: HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE),
    TMCLocation.FALLS_LOWER_ROCK_ITEM2: HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE),
    TMCLocation.FALLS_LOWER_ROCK_ITEM3: HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE),
    TMCLocation.FALLS_LOWER_DIG_CAVE_LEFT_CHEST: And(
        HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE), Has(TMCItem.MOLE_MITTS)
    ),
    TMCLocation.FALLS_LOWER_DIG_CAVE_RIGHT_CHEST: And(
        HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE),
        Has(TMCItem.MOLE_MITTS),
    ),
    # endregion
    # region Lake Hylia
    TMCLocation.HYLIA_SUNKEN_HP: Has(TMCItem.FLIPPERS),
    TMCLocation.HYLIA_DOG_NPC: Has(TMCItem.DOG_FOOD),
    TMCLocation.HYLIA_SMALL_ISLAND_HP: Has(TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_CAPE_CAVE_TOP_RIGHT: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_CAPE_CAVE_BOTTOM_LEFT: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_CAPE_CAVE_TOP_LEFT: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_CAPE_CAVE_TOP_MIDDLE: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_CAPE_CAVE_RIGHT: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_CAPE_CAVE_BOTTOM_RIGHT: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_CAPE_CAVE_BOTTOM_MIDDLE: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_CAPE_CAVE_LON_LON_HP: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_BEANSTALK_FUSION_LEFT_CHEST:  # Fusion 23
    HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_BEANSTALK_FUSION_HP: HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),  # Fusion 23
    TMCLocation.HYLIA_BEANSTALK_FUSION_RIGHT_CHEST:  # Fusion 23
    HasAll(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.HYLIA_MIDDLE_ISLAND_FUSION_DIG_CAVE_CHEST:  # Fusion 34
    And(Has(TMCItem.MOLE_MITTS), cape_extend),
    TMCLocation.HYLIA_BOTTOM_HP: cape_extend,
    TMCLocation.HYLIA_DOJO_HP: cape_extend,
    TMCLocation.HYLIA_DOJO_NPC: And(cape_extend, HasMaxHealth(10), has_sword),
    TMCLocation.HYLIA_CRACK_FUSION_LIBRARI_NPC:  # fusion 12
    And(Has(TMCItem.OCARINA), HasAny(TMCItem.FLIPPERS, TMCItem.ROCS_CAPE)),
    TMCLocation.HYLIA_NORTH_MINISH_HOLE_CHEST: And(lake_minish, Has(TMCItem.FLIPPERS)),
    TMCLocation.HYLIA_SOUTH_MINISH_HOLE_CHEST: And(lake_minish, Has(TMCItem.FLIPPERS)),
    TMCLocation.HYLIA_CABIN_PATH_FUSION_CHEST:  # Fusion 51
    And(lake_minish, cabin_swim),
    TMCLocation.HYLIA_MAYOR_CABIN_ITEM: And(lake_minish, cabin_swim, Has(TMCItem.POWER_BRACELETS)),
    # endregion
    # region Minish Woods
    # Can Pass Trees
    TMCLocation.MINISH_WOODS_GOLDEN_OCTO:  # Fusion 56
    And(access_minish_woods_top_left, has_sword),
    TMCLocation.MINISH_WOODS_WITCH_HUT_ITEM: And(access_minish_woods_top_left, CanPay(60)),
    TMCLocation.WITCH_DIGGING_CAVE_CHEST: And(access_minish_woods_top_left, Has(TMCItem.MOLE_MITTS)),
    TMCLocation.MINISH_WOODS_NORTH_FUSION_CHEST: access_minish_woods_top_left,  # fusion 44
    TMCLocation.MINISH_WOODS_TOP_HP: access_minish_woods_top_left,
    TMCLocation.MINISH_WOODS_WEST_FUSION_CHEST: None,  # fusion 47
    TMCLocation.MINISH_WOODS_LIKE_LIKE_DIGGING_CAVE_LEFT_CHEST: And(Has(TMCItem.MOLE_MITTS), likelike),
    TMCLocation.MINISH_WOODS_LIKE_LIKE_DIGGING_CAVE_RIGHT_CHEST: And(Has(TMCItem.MOLE_MITTS), likelike),
    TMCLocation.MINISH_WOODS_EAST_FUSION_CHEST: None,  # fusion 46
    TMCLocation.MINISH_WOODS_SOUTH_FUSION_CHEST: None,  # fusion 39
    TMCLocation.MINISH_WOODS_BOTTOM_HP: None,
    TMCLocation.MINISH_WOODS_CRACK_FUSION_CHEST: None,  # fusion 4E
    TMCLocation.MINISH_WOODS_MINISH_PATH_FUSION_CHEST: None,  # fusion 37
    TMCLocation.MINISH_VILLAGE_BARREL_HOUSE_ITEM: None,
    TMCLocation.MINISH_VILLAGE_HP: None,
    TMCLocation.MINISH_WOODS_BOMB_MINISH_NPC_1: None,
    TMCLocation.MINISH_WOODS_BOMB_MINISH_NPC_2: None,  # fusion 1C
    TMCLocation.MINISH_WOODS_POST_VILLAGE_FUSION_CHEST: None,  # Fusion 38
    TMCLocation.MINISH_WOODS_FLIPPER_HOLE_MIDDLE_CHEST: Has(TMCItem.FLIPPERS),
    TMCLocation.MINISH_WOODS_FLIPPER_HOLE_RIGHT_CHEST: Has(TMCItem.FLIPPERS),
    TMCLocation.MINISH_WOODS_FLIPPER_HOLE_LEFT_CHEST: Has(TMCItem.FLIPPERS),
    TMCLocation.MINISH_WOODS_FLIPPER_HOLE_HP: Has(TMCItem.FLIPPERS),
    # endregion
    # region Trilby Highlands
    # Can Spin / Flippers / Roc's Cape
    TMCLocation.TRILBY_MIDDLE_FUSION_CHEST: None,  # fusion 5E
    TMCLocation.TRILBY_TOP_FUSION_CHEST: None,  # fusion 52
    TMCLocation.TRILBY_DIG_CAVE_LEFT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.TRILBY_DIG_CAVE_RIGHT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.TRILBY_DIG_CAVE_WATER_FUSION_CHEST:  # fusion 22
    And(Has(TMCItem.MOLE_MITTS), HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS)),
    TMCLocation.TRILBY_SCRUB_NPC: And(has_shield, Has(TMCItem.BOMB_BAG), CanPay(20)),
    # endregion
    # region Western Woods
    TMCLocation.TRILBY_BOMB_CAVE_CHEST: Has(TMCItem.BOMB_BAG),
    # Everything below require Fusion 3F
    # They also are part of the western wood region
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM1: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM2: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM3: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM4: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM5: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM6: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM7: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM8: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM9: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM10: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM11: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM12: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM13: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM14: None,
    TMCLocation.TRILBY_PUDDLE_FUSION_ITEM15: None,
    TMCLocation.WESTERN_WOODS_FUSION_CHEST: None,  # fusion 3A
    TMCLocation.WESTERN_WOODS_TREE_FUSION_HP: None,  # fusion 11
    TMCLocation.WESTERN_WOODS_TOP_DIG1: Has(TMCItem.MOLE_MITTS),  # fusion 48
    TMCLocation.WESTERN_WOODS_TOP_DIG2: Has(TMCItem.MOLE_MITTS),  # fusion 48
    TMCLocation.WESTERN_WOODS_TOP_DIG3: Has(TMCItem.MOLE_MITTS),  # fusion 48
    TMCLocation.WESTERN_WOODS_TOP_DIG4: Has(TMCItem.MOLE_MITTS),  # fusion 48
    TMCLocation.WESTERN_WOODS_TOP_DIG5: Has(TMCItem.MOLE_MITTS),  # fusion 48
    TMCLocation.WESTERN_WOODS_TOP_DIG6: Has(TMCItem.MOLE_MITTS),  # fusion 48
    TMCLocation.WESTERN_WOODS_PERCY_FUSION_MOBLIN: Has(TMCItem.LANTERN),  # fusion 21
    TMCLocation.WESTERN_WOODS_PERCY_FUSION_PERCY: Has(TMCItem.LANTERN),  # fusion 21
    TMCLocation.WESTERN_WOODS_BOTTOM_DIG1: Has(TMCItem.MOLE_MITTS),  # fusion 4C
    TMCLocation.WESTERN_WOODS_BOTTOM_DIG2: Has(TMCItem.MOLE_MITTS),  # fusion 4C
    TMCLocation.WESTERN_WOODS_GOLDEN_OCTO: has_sword,  # fusion 3D
    # All the following require Fusion 24
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_CHEST: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM1: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM2: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM3: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM4: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM5: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM6: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM7: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM8: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM9: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM10: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM11: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM12: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM13: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM14: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM15: None,
    TMCLocation.WESTERN_WOODS_BEANSTALK_FUSION_ITEM16: None,
    # endregion
    # region Crenel
    # Crenel Base = bottle
    TMCLocation.CRENEL_BASE_ENTRANCE_VINE: None,  # Assigned to Trilby so it doesn't require bottle
    TMCLocation.CRENEL_BASE_FAIRY_CAVE_ITEM1: Has(TMCItem.BOMB_BAG),
    TMCLocation.CRENEL_BASE_FAIRY_CAVE_ITEM2: Has(TMCItem.BOMB_BAG),
    TMCLocation.CRENEL_BASE_FAIRY_CAVE_ITEM3: Has(TMCItem.BOMB_BAG),
    TMCLocation.CRENEL_BASE_GREEN_WATER_FUSION_CHEST: Has(TMCItem.BOMB_BAG),  # Fusion 4F
    TMCLocation.CRENEL_BASE_WEST_FUSION_CHEST: HasAny(TMCItem.BOMB_BAG, TMCItem.ROCS_CAPE),  # Fusion 63
    TMCLocation.CRENEL_BASE_WATER_CAVE_LEFT_CHEST: Has(TMCItem.BOMB_BAG),
    # can alternatively require cape if the bomb wall is broken
    TMCLocation.CRENEL_BASE_WATER_CAVE_RIGHT_CHEST: Has(TMCItem.BOMB_BAG),
    # can alternatively require cape if the bomb wall is broken
    TMCLocation.CRENEL_BASE_WATER_CAVE_HP: Has(TMCItem.BOMB_BAG),
    # can alternatively require cape/flippers if the bomb wall is broken
    TMCLocation.CRENEL_BASE_MINISH_VINE_HOLE_CHEST: And(HasAny(TMCItem.BOMB_BAG, TMCItem.ROCS_CAPE), blow_dust),
    TMCLocation.CRENEL_BASE_MINISH_CRACK_CHEST: And(HasAny(TMCItem.BOMB_BAG, TMCItem.ROCS_CAPE), blow_dust),
    TMCLocation.CRENEL_VINE_TOP_GOLDEN_TEKTITE: has_sword,  # Fusion 3B
    TMCLocation.CRENEL_BRIDGE_CAVE_CHEST: Has(TMCItem.BOMB_BAG),
    TMCLocation.CRENEL_FAIRY_CAVE_HP: Has(TMCItem.BOMB_BAG),
    TMCLocation.CRENEL_BELOW_COF_GOLDEN_TEKTITE:  # Fusion 0D
    And(has_sword, mushroom),
    TMCLocation.CRENEL_SCRUB_NPC: And(Has(TMCItem.BOMB_BAG), has_shield, CanPay(40), mushroom),
    TMCLocation.CRENEL_DOJO_LEFT_CHEST: And(Has(TMCItem.GRIP_RING), CanSplit(2, True)),
    TMCLocation.CRENEL_DOJO_RIGHT_CHEST: And(Has(TMCItem.GRIP_RING), CanSplit(2, True)),
    TMCLocation.CRENEL_DOJO_HP: And(Has(TMCItem.GRIP_RING), CanSplit(2, True)),
    TMCLocation.CRENEL_DOJO_NPC: And(Has(TMCItem.GRIP_RING), CanSplit(2, True)),
    TMCLocation.CRENEL_GREAT_FAIRY_NPC: HasAll(TMCItem.GRIP_RING, TMCItem.BOMB_BAG),
    TMCLocation.CRENEL_CLIMB_FUSION_CHEST:  # Fusion 62
    HasAll(TMCItem.GRIP_RING, TMCItem.BOMB_BAG),
    TMCLocation.CRENEL_DIG_CAVE_HP: HasAll(TMCItem.GRIP_RING, TMCItem.MOLE_MITTS),
    TMCLocation.CRENEL_BEANSTALK_FUSION_HP: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_BEANSTALK_FUSION_ITEM1: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_BEANSTALK_FUSION_ITEM2: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_BEANSTALK_FUSION_ITEM3: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_BEANSTALK_FUSION_ITEM4: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_BEANSTALK_FUSION_ITEM5: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_BEANSTALK_FUSION_ITEM6: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_BEANSTALK_FUSION_ITEM7: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_BEANSTALK_FUSION_ITEM8: Has(TMCItem.GRIP_RING),  # Fusion 1A
    TMCLocation.CRENEL_RAIN_PATH_FUSION_CHEST: Has(TMCItem.GRIP_RING),  # Fusion 43
    # endregion
    # region Melari
    TMCLocation.CRENEL_UPPER_BLOCK_CHEST: None,
    TMCLocation.CRENEL_MINES_PATH_FUSION_CHEST: None,  # Fusion 45
    TMCLocation.CRENEL_MELARI_LEFT_DIG: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CRENEL_MELARI_TOP_MIDDLE_DIG: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CRENEL_MELARI_TOP_LEFT_DIG: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CRENEL_MELARI_TOP_RIGHT_DIG: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CRENEL_MELARI_BOTTOM_RIGHT_DIG: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CRENEL_MELARI_BOTTOM_MIDDLE_DIG: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CRENEL_MELARI_BOTTOM_LEFT_DIG: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CRENEL_MELARI_CENTER_DIG: Has(TMCItem.MOLE_MITTS),
    # endregion
    # region Castor Wilds
    TMCLocation.SWAMP_BUTTERFLY_FUSION_ITEM: None,  # Fusion 10
    TMCLocation.SWAMP_CENTER_CAVE_DARKNUT_CHEST: has_weapon_boss,
    TMCLocation.SWAMP_CENTER_CHEST: has_bow,
    TMCLocation.SWAMP_GOLDEN_ROPE: has_sword,  # Fusion 49
    TMCLocation.SWAMP_NEAR_WATERFALL_CAVE_HP: And(has_bow, HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS)),
    TMCLocation.SWAMP_WATERFALL_FUSION_DOJO_NPC:  # Fusion 0C
    And(has_bow, Has(TMCItem.FLIPPERS)),
    TMCLocation.SWAMP_NORTH_CAVE_CHEST: has_bow,
    TMCLocation.SWAMP_DIGGING_CAVE_LEFT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.SWAMP_DIGGING_CAVE_RIGHT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.SWAMP_UNDERWATER_TOP: Has(TMCItem.FLIPPERS),
    TMCLocation.SWAMP_UNDERWATER_MIDDLE: Has(TMCItem.FLIPPERS),
    TMCLocation.SWAMP_UNDERWATER_BOTTOM: Has(TMCItem.FLIPPERS),
    TMCLocation.SWAMP_SOUTH_CAVE_CHEST: Or(HasAny(TMCItem.ROCS_CAPE, TMCItem.FLIPPERS), has_bow),
    TMCLocation.SWAMP_DOJO_HP: Or(
        Has(TMCItem.ROCS_CAPE),
        has_bow,
        HasAll(TMCItem.PEGASUS_BOOTS, TMCItem.FLIPPERS),
        And(swamp_crest, Has(TMCItem.PEGASUS_BOOTS)),
    ),
    TMCLocation.SWAMP_DOJO_NPC: And(
        Or(
            Has(TMCItem.ROCS_CAPE),
            has_bow,
            HasAll(TMCItem.PEGASUS_BOOTS, TMCItem.FLIPPERS),
            And(swamp_crest, Has(TMCItem.PEGASUS_BOOTS)),
        ),
        has_sword,
        HasGroup("Scrolls", 7),
    ),
    TMCLocation.SWAMP_MINISH_FUSION_NORTH_CRACK_CHEST:  # Fusion 4B
    Or(HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE), has_bow),
    TMCLocation.SWAMP_MINISH_MULLDOZER_BIG_CHEST: And(
        Or(HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE), has_bow),
        HasAny(TMCItem.FLIPPERS, TMCItem.GUST_JAR),
        has_weapon,
    ),
    TMCLocation.SWAMP_MINISH_FUSION_NORTH_WEST_CRACK_CHEST:  # Fusion 5B
    And(Or(HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE), has_bow), HasAny(TMCItem.FLIPPERS, TMCItem.GUST_JAR)),
    TMCLocation.SWAMP_MINISH_FUSION_WEST_CRACK_CHEST:  # Fusion 57
    Or(HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE), has_bow),
    TMCLocation.SWAMP_MINISH_FUSION_VINE_CRACK_CHEST:  # Fusion 57 & 3E
    Or(HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE), has_bow),
    TMCLocation.SWAMP_MINISH_FUSION_WATER_HOLE_CHEST:  # Fusion 57
    And(Has(TMCItem.FLIPPERS), Or(HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE), has_bow)),
    TMCLocation.SWAMP_MINISH_FUSION_WATER_HOLE_HP:  # Fusion 57
    And(Has(TMCItem.FLIPPERS), Or(HasAny(TMCItem.PEGASUS_BOOTS, TMCItem.ROCS_CAPE), has_bow)),
    # endregion
    # region Wind Ruins
    # Fusion 06 07 08
    TMCLocation.RUINS_BUTTERFLY_FUSION_ITEM: None,  # Fusion 20
    TMCLocation.RUINS_BOMB_CAVE_CHEST: Has(TMCItem.BOMB_BAG),
    TMCLocation.RUINS_MINISH_HOME_CHEST: None,
    # Everything beyond here requires at least 1 sword to pass the first armos
    TMCLocation.RUINS_PILLARS_FUSION_CHEST: has_sword,  # Fusion 64
    TMCLocation.RUINS_BEAN_STALK_FUSION_BIG_CHEST:  # Fusion 17
    And(has_sword, has_weapon),
    TMCLocation.RUINS_CRACK_FUSION_CHEST: And(has_sword, has_weapon),  # Fusion 41
    TMCLocation.RUINS_MINISH_CAVE_HP: And(has_sword, has_weapon),
    TMCLocation.RUINS_ARMOS_KILL_LEFT_CHEST: And(has_sword, has_weapon),
    TMCLocation.RUINS_ARMOS_KILL_RIGHT_CHEST: And(has_sword, has_weapon),
    TMCLocation.RUINS_GOLDEN_OCTO: And(has_sword, has_weapon),  # Fusion 54
    TMCLocation.RUINS_NEAR_FOW_FUSION_CHEST: And(has_sword, has_weapon),  # Fusion 0A
    # endregion
    # region Royal Valley
    TMCLocation.VALLEY_PRE_VALLEY_FUSION_CHEST: None,  # Fusion 5F
    TMCLocation.VALLEY_GREAT_FAIRY_NPC: Has(TMCItem.BOMB_BAG),
    TMCLocation.VALLEY_LOST_WOODS_CHEST: dark_room,
    TMCLocation.VALLEY_DAMPE_NPC: dark_room,
    # Graveyard locations, require graveyard key and pegasus boots
    TMCLocation.VALLEY_GRAVEYARD_BUTTERFLY_FUSION_ITEM: None,  # Fusion 19
    TMCLocation.VALLEY_GRAVEYARD_LEFT_FUSION_CHEST: None,  # Fusion 5C
    TMCLocation.VALLEY_GRAVEYARD_LEFT_GRAVE_HP: CanSplit(3, True),
    TMCLocation.VALLEY_GRAVEYARD_RIGHT_FUSION_CHEST: None,  # Fusion 5D
    TMCLocation.VALLEY_GRAVEYARD_RIGHT_GRAVE_FUSION_CHEST: None,  # Fusion 30
    # endregion
    # region Dungeon RC
    TMCLocation.CRYPT_GIBDO_LEFT_ITEM: Or(Has(TMCItem.LANTERN), has_weapon),
    TMCLocation.CRYPT_GIBDO_RIGHT_ITEM: Or(Has(TMCItem.LANTERN), has_weapon),
    TMCLocation.CRYPT_LEFT_ITEM: And(CanSplit(3), Has(TMCItem.SMALL_KEY_RC, 1)),
    TMCLocation.CRYPT_RIGHT_ITEM: And(CanSplit(3), Has(TMCItem.SMALL_KEY_RC, 1)),
    # endregion
    # region Upper Falls
    # The first 3 are part of North Field logic, doesn't require falls fusion stone or lantern
    TMCLocation.FALLS_ENTRANCE_HP: cape_extend,
    TMCLocation.FALLS_WATER_DIG_CAVE_FUSION_HP:  # Fusion 1F
    And(Has(TMCItem.MOLE_MITTS), cape_extend),
    TMCLocation.FALLS_WATER_DIG_CAVE_FUSION_CHEST:  # Fusion 1F
    And(Has(TMCItem.MOLE_MITTS), cape_extend),
    # Fusion 09
    # TMCLocation.FALLS_1ST_CAVE_CHEST: None,
    TMCLocation.FALLS_CLIFF_CHEST: CanSplit(3, True),
    TMCLocation.FALLS_SOUTH_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    TMCLocation.FALLS_GOLDEN_TEKTITE: has_sword,  # Fusion 4A
    TMCLocation.FALLS_NORTH_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    # TMCLocation.FALLS_ROCK_FUSION_CHEST: None,  # Fusion 61
    TMCLocation.FALLS_WATERFALL_FUSION_HP: Has(TMCItem.FLIPPERS),  # Fusion 13
    # TMCLocation.FALLS_RUPEE_CAVE_TOP_TOP: None,
    # TMCLocation.FALLS_RUPEE_CAVE_TOP_LEFT: None,
    # TMCLocation.FALLS_RUPEE_CAVE_TOP_MIDDLE: None,
    # TMCLocation.FALLS_RUPEE_CAVE_TOP_RIGHT: None,
    # TMCLocation.FALLS_RUPEE_CAVE_TOP_BOTTOM: None,
    # TMCLocation.FALLS_RUPEE_CAVE_SIDE_TOP: None,
    # TMCLocation.FALLS_RUPEE_CAVE_SIDE_LEFT: None,
    # TMCLocation.FALLS_RUPEE_CAVE_SIDE_RIGHT: None,
    # TMCLocation.FALLS_RUPEE_CAVE_SIDE_BOTTOM: None,
    TMCLocation.FALLS_RUPEE_CAVE_UNDERWATER_TOP_LEFT: Has(TMCItem.FLIPPERS),
    TMCLocation.FALLS_RUPEE_CAVE_UNDERWATER_TOP_RIGHT: Has(TMCItem.FLIPPERS),
    TMCLocation.FALLS_RUPEE_CAVE_UNDERWATER_MIDDLE_LEFT: Has(TMCItem.FLIPPERS),
    TMCLocation.FALLS_RUPEE_CAVE_UNDERWATER_MIDDLE_RIGHT: Has(TMCItem.FLIPPERS),
    TMCLocation.FALLS_RUPEE_CAVE_UNDERWATER_BOTTOM_LEFT: Has(TMCItem.FLIPPERS),
    TMCLocation.FALLS_RUPEE_CAVE_UNDERWATER_BOTTOM_RIGHT: Has(TMCItem.FLIPPERS),
    TMCLocation.FALLS_TOP_CAVE_BOMB_WALL_CHEST: Has(TMCItem.BOMB_BAG),
    # TMCLocation.FALLS_TOP_CAVE_CHEST: None,
    # endregion
    # region Cloud Tops
    TMCLocation.FALLS_BIGGORON: Filtered(
        has_mirror_shield, options=[OptionFilter(Biggoron, Biggoron.option_mirror_shield)]
    )
    | has_shield,
    TMCLocation.CLOUDS_FREE_CHEST: None,
    TMCLocation.CLOUDS_NORTH_EAST_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_NORTH_KILL: And(HasAny(TMCItem.ROCS_CAPE, TMCItem.MOLE_MITTS), shark_kill),
    TMCLocation.CLOUDS_NORTH_WEST_LEFT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_NORTH_WEST_RIGHT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_NORTH_WEST_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_NORTH_WEST_BOTTOM_CHEST: HasAny(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.CLOUDS_SOUTH_LEFT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_SOUTH_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_SOUTH_MIDDLE_CHEST: HasAny(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.CLOUDS_SOUTH_MIDDLE_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_SOUTH_KILL: And(HasAny(TMCItem.ROCS_CAPE, TMCItem.MOLE_MITTS), shark_kill),
    TMCLocation.CLOUDS_SOUTH_RIGHT_CHEST: HasAny(TMCItem.MOLE_MITTS, TMCItem.ROCS_CAPE),
    TMCLocation.CLOUDS_SOUTH_RIGHT_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_SOUTH_EAST_BOTTOM_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    TMCLocation.CLOUDS_SOUTH_EAST_TOP_DIG_SPOT: Has(TMCItem.MOLE_MITTS),
    # endregion
    # region Wind Tribe
    # Doesn't require many special access rules *yet*
    # 1F-2F is accessible due to open fusions
    # Fusion 0F
    TMCLocation.WIND_TRIBE_1F_LEFT_CHEST: None,
    TMCLocation.WIND_TRIBE_1F_RIGHT_CHEST: None,
    TMCLocation.WIND_TRIBE_2F_CHEST: None,
    TMCLocation.WIND_TRIBE_2F_GREGAL_NPC_1: Has(TMCItem.GUST_JAR),
    # Here starts the rules that require access to Cloudtops/Wind Tribe
    # Fusion 01 02 03 04 05
    TMCLocation.WIND_TRIBE_2F_GREGAL_NPC_2: Has(TMCItem.GUST_JAR),
    TMCLocation.WIND_TRIBE_3F_LEFT_CHEST: None,
    TMCLocation.WIND_TRIBE_3F_CENTER_CHEST: None,
    TMCLocation.WIND_TRIBE_3F_RIGHT_CHEST: None,
    TMCLocation.WIND_TRIBE_4F_LEFT_CHEST: None,
    TMCLocation.WIND_TRIBE_4F_RIGHT_CHEST: None,
    # endregion
    # region Dungeon DWS Entrance
    TMCLocation.DEEPWOOD_2F_CHEST: HasAny(TMCItem.LANTERN, TMCItem.GUST_JAR),
    TMCLocation.DEEPWOOD_1F_SLUG_TORCHES_CHEST: None,
    # endregion
    # region Dungeon DWS Barrel
    TMCLocation.DEEPWOOD_1F_BARREL_ROOM_CHEST: blow_dust,
    TMCLocation.DEEPWOOD_1F_WEST_BIG_CHEST: None,
    TMCLocation.DEEPWOOD_1F_WEST_STATUE_PUZZLE_CHEST: None,
    # endregion
    # region Dungeon DWS East
    TMCLocation.DEEPWOOD_1F_EAST_MULLDOZER_FIGHT_ITEM: has_weapon,
    # endregion
    # region Dungeon DWS Backside
    TMCLocation.DEEPWOOD_1F_NORTH_EAST_CHEST: blow_dust,
    TMCLocation.DEEPWOOD_B1_SWITCH_ROOM_BIG_CHEST: None,
    TMCLocation.DEEPWOOD_B1_SWITCH_ROOM_CHEST: HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE),
    TMCLocation.DEEPWOOD_1F_BLUE_WARP_LEFT_CHEST: blow_dust,
    TMCLocation.DEEPWOOD_1F_BLUE_WARP_RIGHT_CHEST: blow_dust,
    TMCLocation.DEEPWOOD_1F_MADDERPILLAR_BIG_CHEST: And(
        has_weapon_boss, Or(Has(TMCItem.SMALL_KEY_DWS, 4), Has(TMCItem.LANTERN))
    ),
    TMCLocation.DEEPWOOD_1F_MADDERPILLAR_HP: Or(
        And(Has(TMCItem.SMALL_KEY_DWS, 4), Has(TMCItem.GUST_JAR)), Has(TMCItem.LANTERN)
    ),
    # endregion
    # region Dungeon DWS Blue Warp
    TMCLocation.DEEPWOOD_1F_BLUE_WARP_HP: None,
    # endregion
    # region Dungeon DWS Red Warp
    TMCLocation.DEEPWOOD_B1_WEST_BIG_CHEST: None,
    # endregion
    # region Dungeon DWS Boss
    TMCLocation.DEEPWOOD_BOSS_ITEM: None,
    TMCLocation.DEEPWOOD_PRIZE: None,
    # endregion
    # region Dungeon COF Main
    TMCLocation.COF_1F_SPIKE_BEETLE_BIG_CHEST: None,
    TMCLocation.COF_1F_ITEM1: None,
    TMCLocation.COF_1F_ITEM2: None,
    TMCLocation.COF_1F_ITEM3: None,
    TMCLocation.COF_1F_ITEM4: None,
    TMCLocation.COF_1F_ITEM5: None,  # FUTURE: grabbed through wall
    TMCLocation.COF_B1_HAZY_ROOM_BIG_CHEST: has_weapon_helm_ghini,
    TMCLocation.COF_B1_HAZY_ROOM_SMALL_CHEST: has_weapon_helm_ghini,
    TMCLocation.COF_B1_ROLLOBITE_CHEST: has_weapon_helm_ghini,
    TMCLocation.COF_B1_ROLLOBITE_PILLAR_CHEST: has_weapon_helm_ghini,
    # endregion
    # region Dungeon COF Minecart Ride
    TMCLocation.COF_B1_SPIKEY_CHUS_PILLAR_CHEST: Has(TMCItem.CANE_OF_PACCI),
    TMCLocation.COF_B1_HP: Has(TMCItem.BOMB_BAG),
    TMCLocation.COF_B1_SPIKEY_CHUS_BIG_CHEST: has_weapon,
    # endregion
    # region Dungeon COF Lava Basement
    TMCLocation.COF_B2_PRE_LAVA_NORTH_CHEST: Has(TMCItem.CANE_OF_PACCI),
    TMCLocation.COF_B2_PRE_LAVA_SOUTH_CHEST: Has(TMCItem.CANE_OF_PACCI),
    TMCLocation.COF_B2_LAVA_ROOM_BLADE_CHEST: HasAny(TMCItem.CANE_OF_PACCI, TMCItem.ROCS_CAPE),
    TMCLocation.COF_B2_LAVA_ROOM_RIGHT_CHEST: HasAny(TMCItem.CANE_OF_PACCI, TMCItem.ROCS_CAPE),
    TMCLocation.COF_B2_LAVA_ROOM_LEFT_CHEST: HasAny(TMCItem.CANE_OF_PACCI, TMCItem.ROCS_CAPE),
    TMCLocation.COF_B2_LAVA_ROOM_BIG_CHEST: HasAny(TMCItem.CANE_OF_PACCI, TMCItem.ROCS_CAPE),
    # endregion
    # region Dungeon COF Boss
    TMCLocation.COF_BOSS_ITEM: None,
    TMCLocation.COF_PRIZE: None,
    # FUTURE: Dungeon Entrance Rando, move out of Dungeon Clear region, require TMCEvent.CLEAR_COF
    TMCLocation.CRENEL_MELARI_NPC: CanReachLocation(TMCLocation.CRENEL_UPPER_BLOCK_CHEST),
    # endregion
    # region Dungeon FOW Entrance
    TMCLocation.FORTRESS_ENTRANCE_1F_LEFT_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.FORTRESS_ENTRANCE_1F_LEFT_WIZZROBE_CHEST: And(Has(TMCItem.MOLE_MITTS), has_weapon_wizzrobe),
    TMCLocation.FORTRESS_ENTRANCE_1F_RIGHT_ITEM: Has(TMCItem.MOLE_MITTS),
    TMCLocation.FORTRESS_LEFT_2F_DIG_CHEST: And(has_bow, has_weapon, Has(TMCItem.MOLE_MITTS)),
    TMCLocation.FORTRESS_LEFT_2F_ITEM1: And(has_bow, has_weapon),
    TMCLocation.FORTRESS_LEFT_2F_ITEM2: And(has_bow, has_weapon),
    TMCLocation.FORTRESS_LEFT_2F_ITEM3: And(has_bow, has_weapon),
    TMCLocation.FORTRESS_LEFT_2F_ITEM4: And(has_bow, has_weapon),
    TMCLocation.FORTRESS_LEFT_2F_ITEM5: And(has_bow, has_weapon),
    # FUTURE: Item 5 can get grabbed through the wall
    TMCLocation.FORTRESS_LEFT_2F_ITEM6: And(has_bow, has_weapon),
    TMCLocation.FORTRESS_LEFT_2F_ITEM7: And(has_bow, has_weapon),
    TMCLocation.FORTRESS_LEFT_3F_SWITCH_CHEST: And(has_bow, has_weapon, Has(TMCItem.MOLE_MITTS)),
    TMCLocation.FORTRESS_LEFT_3F_EYEGORE_BIG_CHEST: And(has_bow, has_weapon),
    TMCLocation.FORTRESS_LEFT_3F_ITEM_DROP: And(has_bow, has_weapon, Or(Has(TMCItem.ROCS_CAPE), CanSplit(2))),
    TMCLocation.FORTRESS_MIDDLE_2F_STATUE_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.FORTRESS_RIGHT_2F_LEFT_CHEST: None,
    TMCLocation.FORTRESS_RIGHT_2F_RIGHT_CHEST: None,
    TMCLocation.FORTRESS_RIGHT_2F_DIG_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.FORTRESS_RIGHT_3F_DIG_CHEST: Has(TMCItem.MOLE_MITTS),
    TMCLocation.FORTRESS_RIGHT_3F_ITEM_DROP: CanSplit(2),
    TMCLocation.FORTRESS_ENTRANCE_1F_RIGHT_HP: CanSplit(2),
    TMCLocation.FORTRESS_BACK_RIGHT_DIG_ROOM_BOTTOM_POT: Or(
        fow_pot, And(Has(TMCItem.SMALL_KEY_FOW, 3), Has(TMCItem.MOLE_MITTS), Or(has_bow, fow_blue_warp))
    ),
    # endregion
    # region Dungeon FOW Past Blue Warp
    TMCLocation.FORTRESS_BACK_LEFT_BIG_CHEST: Has(TMCItem.BOMB_BAG),
    TMCLocation.FORTRESS_BACK_LEFT_SMALL_CHEST: HasAll(TMCItem.BOMB_BAG, TMCItem.MOLE_MITTS),
    # endregion
    # region Dungeon FOW Past Eyegores
    TMCLocation.FORTRESS_MIDDLE_2F_BIG_CHEST: None,
    TMCLocation.FORTRESS_BACK_RIGHT_STATUE_ITEM_DROP: And(Has(TMCItem.SMALL_KEY_FOW, 2), CanSplit(2)),
    TMCLocation.FORTRESS_BACK_RIGHT_MINISH_ITEM_DROP: And(
        Has(TMCItem.SMALL_KEY_FOW, 3), has_weapon, Has(TMCItem.MOLE_MITTS)
    ),
    TMCLocation.FORTRESS_BACK_RIGHT_DIG_ROOM_TOP_POT: And(Has(TMCItem.SMALL_KEY_FOW, 3), Has(TMCItem.MOLE_MITTS)),
    TMCLocation.FORTRESS_BACK_RIGHT_BIG_CHEST: And(Has(TMCItem.SMALL_KEY_FOW, 4), Has(TMCItem.MOLE_MITTS)),
    # endregion
    # region Dungeon FOW Boss
    TMCLocation.FORTRESS_BOSS_ITEM: None,
    TMCLocation.FORTRESS_PRIZE: None,
    # endregion
    # region Dungeon TOD Entrance
    TMCLocation.DROPLETS_ENTRANCE_B2_EAST_ICEBLOCK: None,
    TMCLocation.DROPLETS_ENTRANCE_B2_WEST_ICEBLOCK: StupidToDWestIceblock(),
    # endregion
    # region Dungeon TOD After Big Key
    TMCLocation.DROPLETS_LEFT_PATH_B1_UNDERPASS_ITEM1: None,
    TMCLocation.DROPLETS_LEFT_PATH_B1_UNDERPASS_ITEM2: None,
    TMCLocation.DROPLETS_LEFT_PATH_B1_UNDERPASS_ITEM3: None,
    TMCLocation.DROPLETS_LEFT_PATH_B1_UNDERPASS_ITEM4: None,
    TMCLocation.DROPLETS_LEFT_PATH_B1_UNDERPASS_ITEM5: None,
    TMCLocation.DROPLETS_LEFT_PATH_B1_WATERFALL_BIG_CHEST: None,
    TMCLocation.DROPLETS_LEFT_PATH_B1_WATERFALL_UNDERWATER1: Has(TMCItem.FLIPPERS),
    TMCLocation.DROPLETS_LEFT_PATH_B1_WATERFALL_UNDERWATER2: Has(TMCItem.FLIPPERS),
    TMCLocation.DROPLETS_LEFT_PATH_B1_WATERFALL_UNDERWATER3: Has(TMCItem.FLIPPERS),
    TMCLocation.DROPLETS_LEFT_PATH_B1_WATERFALL_UNDERWATER4: Has(TMCItem.FLIPPERS),
    TMCLocation.DROPLETS_LEFT_PATH_B1_WATERFALL_UNDERWATER5: Has(TMCItem.FLIPPERS),
    TMCLocation.DROPLETS_LEFT_PATH_B1_WATERFALL_UNDERWATER6: Has(TMCItem.FLIPPERS),
    TMCLocation.DROPLETS_LEFT_PATH_B2_WATERFALL_UNDERWATER1: And(
        Has(TMCItem.FLIPPERS), HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE)
    ),
    TMCLocation.DROPLETS_LEFT_PATH_B2_WATERFALL_UNDERWATER2: And(
        Has(TMCItem.FLIPPERS), HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE)
    ),
    TMCLocation.DROPLETS_LEFT_PATH_B2_WATERFALL_UNDERWATER3: And(
        Has(TMCItem.FLIPPERS), HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE)
    ),
    TMCLocation.DROPLETS_LEFT_PATH_B2_WATERFALL_UNDERWATER4: And(
        Has(TMCItem.FLIPPERS), HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE)
    ),
    TMCLocation.DROPLETS_LEFT_PATH_B2_WATERFALL_UNDERWATER5: And(
        Has(TMCItem.FLIPPERS), HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE)
    ),
    TMCLocation.DROPLETS_LEFT_PATH_B2_WATERFALL_UNDERWATER6: And(
        Has(TMCItem.FLIPPERS), HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE)
    ),
    TMCLocation.DROPLETS_LEFT_PATH_B2_UNDERWATER_POT: And(
        Has(TMCItem.FLIPPERS), Or(tod_blue_warp, HasAny(TMCItem.GUST_JAR, TMCItem.ROCS_CAPE))
    ),
    TMCLocation.DROPLETS_RIGHT_PATH_B1_1ST_CHEST: tod_right_ice,
    TMCLocation.DROPLETS_RIGHT_PATH_B1_2ND_CHEST: tod_right_ice,
    TMCLocation.DROPLETS_RIGHT_PATH_B1_POT: tod_right_ice,
    TMCLocation.DROPLETS_RIGHT_PATH_B3_FROZEN_CHEST: tod_right_ice,
    TMCLocation.DROPLETS_RIGHT_PATH_B1_BLU_CHU_BIG_CHEST: And(
        tod_right_ice, Has(TMCItem.SMALL_KEY_TOD, 4), Has(TMCItem.GUST_JAR), has_weapon_boss
    ),
    TMCLocation.DROPLETS_RIGHT_PATH_B2_FROZEN_CHEST: Has(TMCItem.LANTERN),
    TMCLocation.DROPLETS_RIGHT_PATH_B2_DARK_MAZE_BOTTOM_CHEST: And(has_weapon_scissor, Has(TMCItem.LANTERN)),
    TMCLocation.DROPLETS_RIGHT_PATH_B2_MULLDOZERS_ITEM_DROP: And(
        has_weapon_scissor,
        has_weapon,  # redundancy for future settings
        HasAll(TMCItem.LANTERN, TMCItem.BOMB_BAG),
    ),
    TMCLocation.DROPLETS_RIGHT_PATH_B2_DARK_MAZE_TOP_RIGHT_CHEST: And(has_weapon_scissor, Has(TMCItem.LANTERN)),
    TMCLocation.DROPLETS_RIGHT_PATH_B2_DARK_MAZE_TOP_LEFT_CHEST: And(has_weapon_scissor, Has(TMCItem.LANTERN)),
    # endregion
    # region Dungeon TOD Lilypad Basement
    TMCLocation.DROPLETS_LEFT_PATH_B2_ICE_MADDERPILLAR_BIG_CHEST: And(has_weapon_boss, Has(TMCItem.GUST_JAR)),
    TMCLocation.DROPLETS_LEFT_PATH_B2_ICE_PLAIN_FROZEN_CHEST: And(
        Has(TMCItem.LANTERN), HasAny(TMCItem.FLIPPERS, TMCItem.GUST_JAR, TMCItem.ROCS_CAPE)
    ),
    TMCLocation.DROPLETS_LEFT_PATH_B2_ICE_PLAIN_CHEST: HasAny(TMCItem.FLIPPERS, TMCItem.GUST_JAR, TMCItem.ROCS_CAPE),
    TMCLocation.DROPLETS_LEFT_PATH_B2_LILYPAD_CORNER_FROZEN_CHEST: HasAll(TMCItem.GUST_JAR, TMCItem.LANTERN),
    # endregion
    # region Dungeon TOD Dark Maze End
    TMCLocation.DROPLETS_RIGHT_PATH_B2_UNDERPASS_ITEM1: None,
    TMCLocation.DROPLETS_RIGHT_PATH_B2_UNDERPASS_ITEM2: None,
    TMCLocation.DROPLETS_RIGHT_PATH_B2_UNDERPASS_ITEM3: None,
    TMCLocation.DROPLETS_RIGHT_PATH_B2_UNDERPASS_ITEM4: None,
    TMCLocation.DROPLETS_RIGHT_PATH_B2_UNDERPASS_ITEM5: None,
    # endregion
    # region Dungeon TOD Boss
    TMCLocation.DROPLETS_BOSS_ITEM: None,
    TMCLocation.DROPLETS_PRIZE: None,
    # endregion
    # region Dungeon POW 1st Half 1F
    TMCLocation.PALACE_1ST_HALF_1F_GRATE_CHEST: Has(TMCItem.ROCS_CAPE),
    TMCLocation.PALACE_1ST_HALF_1F_WIZZROBE_BIG_CHEST: And(
        has_weapon_wizzrobe, Or(has_boomerang, HasAny(TMCItem.ROCS_CAPE, TMCItem.BOMB_BAG))
    ),
    # endregion
    # region Dungeon POW 1st Half 2F
    TMCLocation.PALACE_1ST_HALF_2F_ITEM1: None,
    TMCLocation.PALACE_1ST_HALF_2F_ITEM2: None,
    TMCLocation.PALACE_1ST_HALF_2F_ITEM3: None,
    TMCLocation.PALACE_1ST_HALF_2F_ITEM4: None,
    TMCLocation.PALACE_1ST_HALF_2F_ITEM5: None,
    # endregion
    # region Dungeon POW 1st Half 3F
    TMCLocation.PALACE_1ST_HALF_3F_POT_PUZZLE_ITEM_DROP: And(Has(TMCItem.CANE_OF_PACCI), pow_pot),
    # endregion
    # region Dungeon POW 1st Half 4F
    TMCLocation.PALACE_1ST_HALF_4F_BOW_MOBLINS_CHEST: None,
    # endregion
    # region Dungeon POW 1st Half 5F
    TMCLocation.PALACE_1ST_HALF_5F_BALL_AND_CHAIN_SOLDIERS_ITEM_DROP: has_weapon,
    TMCLocation.PALACE_1ST_HALF_5F_FAN_LOOP_CHEST: And(
        Has(TMCItem.ROCS_CAPE), Has(TMCItem.SMALL_KEY_POW, 5), has_weapon
    ),
    TMCLocation.PALACE_1ST_HALF_5F_BIG_CHEST: Has(TMCItem.SMALL_KEY_POW, 6),
    # endregion
    # region Dungeon POW 2nd Half 1F
    TMCLocation.PALACE_2ND_HALF_1F_DARK_ROOM_BIG_CHEST: None,
    # endregion
    # region Dungeon POW 2nd Half 2F
    TMCLocation.PALACE_2ND_HALF_1F_DARK_ROOM_SMALL_CHEST: None,
    TMCLocation.PALACE_2ND_HALF_2F_MANY_ROLLERS_CHEST: And(CanSplit(3), Has(TMCItem.ROCS_CAPE)),  # FUTURE: Bomb Trick
    # endregion
    # region Dungeon POW 2nd Half 3F
    TMCLocation.PALACE_2ND_HALF_2F_TWIN_WIZZROBES_CHEST: has_weapon_wizzrobe,
    TMCLocation.PALACE_2ND_HALF_3F_FIRE_WIZZROBES_BIG_CHEST: has_weapon_wizzrobe,
    # endregion
    # region Dungeon POW 2nd Half 4F
    TMCLocation.PALACE_2ND_HALF_4F_HP: Has(TMCItem.ROCS_CAPE),
    TMCLocation.PALACE_2ND_HALF_4F_SWITCH_HIT_CHEST: pow_red_chest,
    # endregion
    # region Dungeon POW End
    TMCLocation.PALACE_2ND_HALF_5F_BOMBAROSSA_CHEST: None,
    TMCLocation.PALACE_2ND_HALF_4F_BLOCK_MAZE_CHEST: None,
    TMCLocation.PALACE_2ND_HALF_5F_RIGHT_SIDE_CHEST: None,
    # endregion
    # region Dungeon POW Boss
    TMCLocation.PALACE_BOSS_ITEM: None,
    TMCLocation.PALACE_PRIZE: None,
    # endregion
    # region Sanctuary
    TMCLocation.PEDESTAL_REQUIREMENT_REWARD: CanActivatePedestal(),
    TMCLocation.SANCTUARY_PEDESTAL_ITEM1: HasGroup("Elements", 2),
    TMCLocation.SANCTUARY_PEDESTAL_ITEM2: HasGroup("Elements", 3),
    TMCLocation.SANCTUARY_PEDESTAL_ITEM3: HasGroup("Elements", 4),
    # endregion
    # region Dungeon DHC B2
    TMCLocation.DHC_B2_KING: CanSplit(4),
    # endregion
    # region Dungeon DHC B1
    TMCLocation.DHC_B1_BIG_CHEST: None,
    # endregion
    # region Dungeon DHC Entrance
    TMCLocation.DHC_1F_BLADE_CHEST: And(dhc_cannons, dhc_pads),
    # endregion
    # region Dungeon DHC 1F
    TMCLocation.DHC_1F_THRONE_BIG_CHEST: None,
    # endregion
    # region Dungeon DHC Blue Warp
    TMCLocation.DHC_3F_NORTH_WEST_CHEST: And(has_weapon_boss, has_bow),
    TMCLocation.DHC_3F_NORTH_EAST_CHEST: And(has_weapon_boss, Has(TMCItem.LANTERN)),
    TMCLocation.DHC_3F_SOUTH_WEST_CHEST: And(has_weapon_boss, dhc_south_towers),
    TMCLocation.DHC_3F_SOUTH_EAST_CHEST: And(has_weapon_boss, dhc_south_towers, dhc_spin),
    TMCLocation.DHC_2F_BLUE_WARP_BIG_CHEST: And(Has(TMCItem.SMALL_KEY_DHC, 5), CanSplit(4)),
    # endregion
}
