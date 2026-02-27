"""
Pokemon team management system.
Handles team composition, validation, and management across different game eras.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime
import logging

from ..core.pokemon import Pokemon, ShadowPokemon
from ..core.types import PokemonType


class TeamFormat(Enum):
    """Pokemon battle formats."""
    SINGLE = "single"           # 1v1 battles
    DOUBLE = "double"           # 2v2 battles
    TRIPLE = "triple"           # 3v3 battles (Gen 5)
    ROTATION = "rotation"       # Rotation battles (Gen 5)
    MULTI = "multi"             # Multi battles (2 trainers vs 2 trainers)


class TeamEra(Enum):
    """Game era for team compatibility."""
    # GameCube Era
    COLOSSEUM = "colosseum"           # Pokemon Colosseum
    XD_GALE = "xd_gale"              # Pokemon XD: Gale of Darkness
    POKEMON_BOX = "pokemon_box"       # Pokemon Box: Ruby & Sapphire
    
    # Wii Era
    BATTLE_REVOLUTION = "battle_revolution"  # Pokemon Battle Revolution
    POKEMON_RANCH = "pokemon_ranch"          # Pokemon Ranch
    
    # DS Era
    DIAMOND_PEARL = "diamond_pearl"          # Diamond/Pearl
    PLATINUM = "platinum"                    # Platinum
    HEARTGOLD_SOULSILVER = "heartgold_soulsilver"  # HeartGold/SoulSilver
    BLACK_WHITE = "black_white"              # Black/White
    BLACK2_WHITE2 = "black2_white2"          # Black 2/White 2
    
    # 3DS Era
    X_Y = "x_y"                              # X/Y
    OMEGA_RUBY_ALPHA_SAPPHIRE = "omega_ruby_alpha_sapphire"  # ORAS
    SUN_MOON = "sun_moon"                    # Sun/Moon
    ULTRA_SUN_ULTRA_MOON = "ultra_sun_ultra_moon"  # USUM
    
    # Switch Era
    SWORD_SHIELD = "sword_shield"            # Sword/Shield
    BRILLIANT_DIAMOND_SHINING_PEARL = "brilliant_diamond_shining_pearl"  # BDSP
    LEGENDS_ARCEUS = "legends_arceus"        # Legends Arceus
    SCARLET_VIOLET = "scarlet_violet"        # Scarlet/Violet
    
    # Legacy groupings for backward compatibility
    GAMECUBE = "gamecube"       # Colosseum, XD: Gale of Darkness
    WII = "wii"                 # Battle Revolution, PBR
    DS = "ds"                   # Diamond/Pearl, HeartGold/SoulSilver
    DS3 = "3ds"                 # Black/White, X/Y, Omega Ruby/Alpha Sapphire
    SWITCH = "switch"           # Sun/Moon, Sword/Shield, Scarlet/Violet


class GameSpecificFeatures:
    """Handles era-specific game mechanics and features."""
    
    @staticmethod
    def get_era_features(era: TeamEra) -> Dict[str, Any]:
        """Get features available in a specific game era."""
        features = {
            'shadow_pokemon': False,
            'mega_evolution': False,
            'z_moves': False,
            'dynamax': False,
            'terastallization': False,
            'max_pokemon': 6,
            'max_level': 100,
            'formats': [TeamFormat.SINGLE],
            'special_mechanics': []
        }
        
        if era in [TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
            features.update({
                'shadow_pokemon': True,
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Shadow Pokemon', 'Purification', 'Shadow Moves']
            })
        elif era == TeamEra.POKEMON_BOX:
            features.update({
                'max_pokemon': 1500,  # Pokemon Box can store up to 1500 Pokemon
                'special_mechanics': ['Storage Management', 'Transfer to GBA']
            })
        elif era == TeamEra.BATTLE_REVOLUTION:
            features.update({
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': [
                    'WiFi Battles', 
                    'Custom Rules', 
                    '3D Battle Stadiums',
                    'Pokemon Transfer from DS',
                    'Rental Pokemon',
                    'Colosseum Battles',
                    'Pass Power System',
                    'Battle Passes',
                    'Custom Trainer Cards',
                    'WiFi Plaza',
                    'Friend Roster',
                    'Battle Records',
                    'Pokemon Stats Display',
                    'Move Animations',
                    'Custom Music'
                ],
                'max_pokemon': 6,
                'max_level': 100,
                'battle_stadiums': [
                    'Gateway Colosseum',
                    'Main Street Colosseum', 
                    'Neon Colosseum',
                    'Crystal Colosseum',
                    'Sunset Colosseum',
                    'Courtyard Colosseum',
                    'Stargazer Colosseum',
                    'Waterfall Colosseum',
                    'Lagoon Colosseum',
                    'Crystal Colosseum',
                    'Sunny Park Colosseum',
                    'Magma Colosseum',
                    'Hail Colosseum',
                    'Ruin Colosseum',
                    'Factory Colosseum',
                    'Castle Colosseum'
                ]
            })
        elif era in [TeamEra.DIAMOND_PEARL, TeamEra.PLATINUM]:
            features.update({
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Physical/Special Split', 'WiFi Battles']
            })
        elif era == TeamEra.HEARTGOLD_SOULSILVER:
            features.update({
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Pokemon Following', 'Pokeathlon', 'WiFi Battles']
            })
        elif era in [TeamEra.BLACK_WHITE, TeamEra.BLACK2_WHITE2]:
            features.update({
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE, TeamFormat.TRIPLE, TeamFormat.ROTATION],
                'special_mechanics': ['Triple Battles', 'Rotation Battles', 'Hidden Abilities']
            })
        elif era == TeamEra.X_Y:
            features.update({
                'mega_evolution': True,
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Mega Evolution', 'Fairy Type', 'Sky Battles']
            })
        elif era == TeamEra.OMEGA_RUBY_ALPHA_SAPPHIRE:
            features.update({
                'mega_evolution': True,
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Mega Evolution', 'Primal Reversion', 'Soaring']
            })
        elif era in [TeamEra.SUN_MOON, TeamEra.ULTRA_SUN_ULTRA_MOON]:
            features.update({
                'z_moves': True,
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Z-Moves', 'Alolan Forms', 'Ultra Beasts']
            })
        elif era == TeamEra.SWORD_SHIELD:
            features.update({
                'dynamax': True,
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Dynamax', 'Gigantamax', 'Max Raid Battles']
            })
        elif era == TeamEra.BRILLIANT_DIAMOND_SHINING_PEARL:
            features.update({
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Grand Underground', 'Ramanas Park']
            })
        elif era == TeamEra.LEGENDS_ARCEUS:
            features.update({
                'max_pokemon': 6,
                'max_level': 100,
                'formats': [TeamFormat.SINGLE],  # No traditional battles
                'special_mechanics': ['Noble Pokemon', 'Alpha Pokemon', 'Crafting']
            })
        elif era == TeamEra.SCARLET_VIOLET:
            features.update({
                'terastallization': True,
                'formats': [TeamFormat.SINGLE, TeamFormat.DOUBLE],
                'special_mechanics': ['Terastallization', 'Tera Raid Battles', 'Paradox Pokemon']
            })
        
        return features
    
    @staticmethod
    def validate_era_compatibility(pokemon: 'Pokemon', era: TeamEra) -> List[str]:
        """Validate if a Pokemon is compatible with a specific era."""
        issues = []
        features = GameSpecificFeatures.get_era_features(era)
        
        # Check if Pokemon exists in this era
        if era in [TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
            if pokemon.species_id > 386:  # Only up to Gen 3
                issues.append(f"{pokemon.name} is not available in {era.value}")
        
        elif era in [TeamEra.DIAMOND_PEARL, TeamEra.PLATINUM]:
            if pokemon.species_id > 493:  # Only up to Gen 4
                issues.append(f"{pokemon.name} is not available in {era.value}")
        
        elif era in [TeamEra.BLACK_WHITE, TeamEra.BLACK2_WHITE2]:
            if pokemon.species_id > 649:  # Only up to Gen 5
                issues.append(f"{pokemon.name} is not available in {era.value}")
        
        # Check for era-specific mechanics
        if not features['mega_evolution'] and hasattr(pokemon, 'mega_evolution'):
            issues.append(f"Mega Evolution is not available in {era.value}")
        
        if not features['z_moves'] and hasattr(pokemon, 'z_moves'):
            issues.append(f"Z-Moves are not available in {era.value}")
        
        if not features['dynamax'] and hasattr(pokemon, 'dynamax'):
            issues.append(f"Dynamax is not available in {era.value}")
        
        if not features['terastallization'] and hasattr(pokemon, 'tera_type'):
            issues.append(f"Terastallization is not available in {era.value}")
        
        return issues


@dataclass
class TeamSlot:
    """A single slot in a Pokemon team."""
    pokemon: Optional[Pokemon] = None
    nickname: Optional[str] = None
    item: Optional[str] = None
    is_active: bool = True
    position: int = 0
    
    def __post_init__(self):
        """Validate team slot parameters."""
        if self.pokemon is not None and not isinstance(self.pokemon, (Pokemon, ShadowPokemon)):
            raise ValueError("Pokemon must be a valid Pokemon or ShadowPokemon instance")
        
        if self.nickname is not None and not isinstance(self.nickname, str):
            raise ValueError("Nickname must be a string")
        
        if self.item is not None and not isinstance(self.item, str):
            raise ValueError("Item must be a string")
        
        if not isinstance(self.is_active, bool):
            raise ValueError("is_active must be a boolean")
        
        if not isinstance(self.position, int) or self.position < 0:
            raise ValueError("Position must be a non-negative integer")
    
    def is_empty(self) -> bool:
        """Check if the slot is empty."""
        return self.pokemon is None
    
    def get_display_name(self) -> str:
        """Get the display name (nickname or Pokemon name)."""
        if self.nickname:
            return self.nickname
        return self.pokemon.name if self.pokemon else "Empty"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert slot to dictionary for serialization."""
        return {
            'pokemon': self.pokemon.to_dict() if self.pokemon else None,
            'nickname': self.nickname,
            'item': self.item,
            'is_active': self.is_active,
            'position': self.position
        }
    
    def __str__(self) -> str:
        """String representation of the team slot."""
        if self.is_empty():
            return f"Slot {self.position + 1}: Empty"
        
        item_text = f" @ {self.item}" if self.item else ""
        return f"Slot {self.position + 1}: {self.get_display_name()}{item_text}"


class PokemonTeam:
    """Comprehensive Pokemon team management class."""
    
    def __init__(
        self,
        name: str = "My Team",
        format: TeamFormat = TeamFormat.SINGLE,
        era: TeamEra = TeamEra.SWITCH,
        max_size: int = 6,
        description: str = ""
    ):
        """
        Initialize a Pokemon team.
        
        Args:
            name: Team name
            format: Battle format
            era: Game era for compatibility
            max_size: Maximum team size
            description: Team description
        """
        # Validate parameters
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Team name must be a non-empty string")
        
        if not isinstance(format, TeamFormat):
            raise ValueError("Format must be a valid TeamFormat enum value")
        
        if not isinstance(era, TeamEra):
            raise ValueError("Era must be a valid TeamEra enum value")
        
        if not isinstance(max_size, int) or max_size < 1 or max_size > 12:
            raise ValueError("Max size must be between 1 and 12")
        
        # Set basic properties
        self.name = name.strip()
        self.format = format
        self.era = era
        self.max_size = max_size
        self.description = description.strip()
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        
        # Initialize team slots
        self.slots: List[TeamSlot] = []
        for i in range(max_size):
            self.slots.append(TeamSlot(position=i))
    
    def add_pokemon(
        self,
        pokemon: Pokemon,
        position: Optional[int] = None,
        nickname: Optional[str] = None,
        item: Optional[str] = None
    ) -> bool:
        """
        Add a Pokemon to the team.
        
        Args:
            pokemon: Pokemon to add
            position: Specific position (None for first available)
            nickname: Custom nickname
            item: Held item
            
        Returns:
            True if Pokemon was added successfully
        """
        if not isinstance(pokemon, (Pokemon, ShadowPokemon)):
            raise ValueError("Pokemon must be a valid Pokemon or ShadowPokemon instance")
        
        # Check era compatibility
        if not self._is_pokemon_compatible(pokemon):
            raise ValueError(f"Pokemon {pokemon.name} is not compatible with {self.era.value} era")
        
        # Find position
        if position is not None:
            if position < 0 or position >= self.max_size:
                raise ValueError(f"Position {position} is out of range")
            target_slot = self.slots[position]
        else:
            # Find first empty slot
            target_slot = self._find_empty_slot()
            if target_slot is None:
                raise ValueError("Team is full")
        
        # Add Pokemon to slot
        target_slot.pokemon = pokemon
        target_slot.nickname = nickname
        target_slot.item = item
        target_slot.is_active = True
        
        self.modified_at = datetime.now()
        
        # Log the addition
        from ..utils.logging_config import get_logger
        logger = get_logger(f'ptb.team.{self.name.lower().replace(" ", "_")}')
        logger.info(f"Added {pokemon.name} to team {self.name} at position {target_slot.position}")
        
        return True
    
    def remove_pokemon(self, position: int) -> bool:
        """
        Remove a Pokemon from the team.
        
        Args:
            position: Position of Pokemon to remove
            
        Returns:
            True if Pokemon was removed successfully
        """
        if position < 0 or position >= self.max_size:
            raise ValueError(f"Position {position} is out of range")
        
        slot = self.slots[position]
        if slot.is_empty():
            return False
        
        # Clear slot
        slot.pokemon = None
        slot.nickname = None
        slot.item = None
        slot.is_active = False
        
        self.modified_at = datetime.now()
        return True
    
    def get_pokemon(self, position: int) -> Optional[Pokemon]:
        """Get Pokemon at specified position."""
        if position < 0 or position >= self.max_size:
            return None
        return self.slots[position].pokemon
    
    def get_active_pokemon(self) -> List[Pokemon]:
        """Get list of active Pokemon in the team."""
        return [slot.pokemon for slot in self.slots if slot.pokemon and slot.is_active]
    
    def get_team_size(self) -> int:
        """Get current team size."""
        return len([slot for slot in self.slots if not slot.is_empty()])
    
    def is_full(self) -> bool:
        """Check if team is full."""
        return self.get_team_size() >= self.max_size
    
    def is_empty(self) -> bool:
        """Check if team is empty."""
        return self.get_team_size() == 0
    
    def get_team_summary(self) -> Dict[str, Any]:
        """Get comprehensive team summary."""
        active_pokemon = self.get_active_pokemon()
        
        # Type coverage analysis
        type_coverage = self._analyze_type_coverage(active_pokemon)
        
        # Stat analysis
        stat_totals = self._analyze_stats(active_pokemon)
        
        # Era-specific features
        era_features = GameSpecificFeatures.get_era_features(self.era)
        
        return {
            'name': self.name,
            'format': self.format.value,
            'era': self.era.value,
            'size': self.get_team_size(),
            'max_size': self.max_size,
            'type_coverage': type_coverage,
            'stat_totals': stat_totals,
            'era_features': era_features,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat()
        }
    
    def get_era_features(self) -> Dict[str, Any]:
        """Get features available in the team's era."""
        return GameSpecificFeatures.get_era_features(self.era)
    
    def validate_era_compatibility(self) -> List[str]:
        """Validate all Pokemon in the team for era compatibility."""
        issues = []
        for slot in self.slots:
            if slot.pokemon:
                slot_issues = GameSpecificFeatures.validate_era_compatibility(slot.pokemon, self.era)
                issues.extend(slot_issues)
        return issues
    
    def _is_pokemon_compatible(self, pokemon: Pokemon) -> bool:
        """Check if Pokemon is compatible with team era."""
        # Use the new GameSpecificFeatures for validation
        compatibility_issues = GameSpecificFeatures.validate_era_compatibility(pokemon, self.era)
        return len(compatibility_issues) == 0
    
    def _find_empty_slot(self) -> Optional[TeamSlot]:
        """Find first empty slot in the team."""
        for slot in self.slots:
            if slot.is_empty():
                return slot
        return None
    
    def _analyze_type_coverage(self, pokemon_list: List[Pokemon]) -> Dict[str, int]:
        """Analyze type coverage of the team."""
        type_counts = {}
        for pokemon in pokemon_list:
            for pokemon_type in pokemon.types:
                type_name = pokemon_type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return type_counts
    
    def _analyze_stats(self, pokemon_list: List[Pokemon]) -> Dict[str, Any]:
        """Analyze total stats of the team."""
        if not pokemon_list:
            return {}
        
        stat_totals = {}
        for pokemon in pokemon_list:
            for stat_name, stat_value in pokemon.stats.get_all_stats().items():
                stat_totals[stat_name] = stat_totals.get(stat_name, 0) + stat_value
        
        # Calculate averages
        team_size = len(pokemon_list)
        stat_averages = {stat: total / team_size for stat, total in stat_totals.items()}
        
        return {
            'totals': stat_totals,
            'averages': stat_averages
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert team to dictionary for serialization."""
        return {
            'name': self.name,
            'format': self.format.value,
            'era': self.era.value,
            'max_size': self.max_size,
            'description': self.description,
            'slots': [slot.to_dict() for slot in self.slots],
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat()
        }
    
    def save_to_file(self, filename: str) -> bool:
        """Save team to JSON file."""
        try:
            with open(filename, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving team: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, filename: str) -> 'PokemonTeam':
        """Load team from JSON file."""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # Create team instance
            team = cls(
                name=data['name'],
                format=TeamFormat(data['format']),
                era=TeamEra(data['era']),
                max_size=data['max_size'],
                description=data.get('description', '')
            )
            
            # Load Pokemon into slots
            for i, slot_data in enumerate(data['slots']):
                if slot_data['pokemon']:
                    # Reconstruct Pokemon from saved data
                    p_data = slot_data['pokemon']
                    from ..core.pokemon import PokemonStats, PokemonEV, PokemonIV, PokemonNature, PokemonStatus
                    base_stats = PokemonStats(**p_data.get('base_stats', {}))
                    evs = PokemonEV(**p_data.get('evs', {}))
                    ivs = PokemonIV(**p_data.get('ivs', {}))
                    is_shadow = p_data.get('is_shadow', False)
                    if is_shadow:
                        from ..core.pokemon import ShadowPokemon
                        pokemon = ShadowPokemon(
                            name=p_data['name'],
                            species_id=p_data['species_id'],
                            level=p_data['level'],
                            nature=PokemonNature(p_data['nature']),
                            base_stats=base_stats,
                            evs=evs,
                            ivs=ivs,
                            moves=p_data.get('moves', []),
                            ability=p_data.get('ability'),
                            shadow_level=p_data.get('shadow_level', 1),
                            purification_progress=p_data.get('purification_progress', 0.0)
                        )
                    else:
                        pokemon = Pokemon(
                            name=p_data['name'],
                            species_id=p_data['species_id'],
                            level=p_data['level'],
                            nature=PokemonNature(p_data['nature']),
                            base_stats=base_stats,
                            evs=evs,
                            ivs=ivs,
                            moves=p_data.get('moves', []),
                            ability=p_data.get('ability'),
                            status=PokemonStatus(p_data.get('status', 'normal')),
                            game_era=p_data.get('game_era', 'modern')
                        )
                    team.add_pokemon(
                        pokemon,
                        position=i,
                        nickname=slot_data.get('nickname'),
                        item=slot_data.get('item')
                    )
            
            return team
        except Exception as e:
            raise ValueError(f"Error loading team from file: {e}")
    
    def __str__(self) -> str:
        """String representation of the team."""
        lines = [f"Team: {self.name} ({self.format.value}, {self.era.value})"]
        lines.append(f"Size: {self.get_team_size()}/{self.max_size}")
        lines.append("-" * 40)
        
        for slot in self.slots:
            if not slot.is_empty():
                lines.append(str(slot))
        
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        """Detailed representation of the team."""
        return f"PokemonTeam(name='{self.name}', format={self.format.value}, era={self.era.value})"
