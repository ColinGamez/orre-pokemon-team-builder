"""
Core Pokemon class with comprehensive validation and GameCube era support.
Includes Shadow Pokemon mechanics for Colosseum and XD games.
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import json
import logging

if TYPE_CHECKING:
    from .types import PokemonType

logger = logging.getLogger(__name__)


class PokemonStatus(Enum):
    """Pokemon status conditions."""
    NORMAL = "normal"
    SLEEP = "sleep"
    POISON = "poison"
    BURN = "burn"
    FREEZE = "freeze"
    PARALYSIS = "paralysis"
    CONFUSION = "confusion"
    SHADOW = "shadow"  # GameCube era specific


class PokemonNature(Enum):
    """Pokemon natures affecting stat growth."""
    HARDY = "hardy"
    LONELY = "lonely"
    BRAVE = "brave"
    ADAMANT = "adamant"
    NAUGHTY = "naughty"
    BOLD = "bold"
    DOCILE = "docile"
    RELAXED = "relaxed"
    IMPISH = "impish"
    LAX = "lax"
    TIMID = "timid"
    HASTY = "hasty"
    SERIOUS = "serious"
    JOLLY = "jolly"
    NAIVE = "naive"
    MODEST = "modest"
    MILD = "mild"
    QUIET = "quiet"
    BASHFUL = "bashful"
    RASH = "rash"
    CALM = "calm"
    GENTLE = "gentle"
    SASSY = "sassy"
    CAREFUL = "careful"
    QUIRKY = "quirky"


@dataclass
class PokemonStats:
    """Pokemon base stats and calculated stats."""
    hp: int = 0
    attack: int = 0
    defense: int = 0
    special_attack: int = 0
    special_defense: int = 0
    speed: int = 0
    
    def __post_init__(self):
        """Validate stats are within valid ranges."""
        for stat_name, value in self.__dict__.items():
            if not isinstance(value, int):
                raise ValueError(f"{stat_name} must be an integer, got {type(value)}")
            if value < 0 or value > 255:
                raise ValueError(f"{stat_name} must be between 0 and 255, got {value}")
    
    def get_all_stats(self) -> Dict[str, int]:
        """Get all stats as a dictionary."""
        return {
            'hp': self.hp,
            'attack': self.attack,
            'defense': self.defense,
            'special_attack': self.special_attack,
            'special_defense': self.special_defense,
            'speed': self.speed
        }


@dataclass
class PokemonEV:
    """Pokemon Effort Values (0-255 per stat, max 510 total)."""
    hp: int = 0
    attack: int = 0
    defense: int = 0
    special_attack: int = 0
    special_defense: int = 0
    speed: int = 0
    
    def __post_init__(self):
        """Validate EV values and total."""
        total = sum(self.__dict__.values())
        if total > 510:
            raise ValueError(f"Total EVs cannot exceed 510, got {total}")
        
        for stat_name, value in self.__dict__.items():
            if not isinstance(value, int):
                raise ValueError(f"{stat_name} EV must be an integer, got {type(value)}")
            if value < 0 or value > 255:
                raise ValueError(f"{stat_name} EV must be between 0 and 255, got {value}")


@dataclass
class PokemonIV:
    """Pokemon Individual Values (0-31 per stat)."""
    hp: int = 0
    attack: int = 0
    defense: int = 0
    special_attack: int = 0
    special_defense: int = 0
    speed: int = 0
    
    def __post_init__(self):
        """Validate IV values."""
        for stat_name, value in self.__dict__.items():
            if not isinstance(value, int):
                raise ValueError(f"{stat_name} IV must be an integer, got {type(value)}")
            if value < 0 or value > 31:
                raise ValueError(f"{stat_name} IV must be between 0 and 31, got {value}")


class Pokemon:
    """Core Pokemon class with comprehensive validation."""
    
    def __init__(
        self,
        name: str,
        species_id: int,
        level: int = 1,
        nature: PokemonNature = PokemonNature.HARDY,
        base_stats: Optional[PokemonStats] = None,
        evs: Optional[PokemonEV] = None,
        ivs: Optional[PokemonIV] = None,
        moves: Optional[List[str]] = None,
        ability: Optional[str] = None,
        status: PokemonStatus = PokemonStatus.NORMAL,
        game_era: str = "modern",
        is_shiny: bool = False
    ):
        """
        Initialize a Pokemon with comprehensive validation.
        
        Args:
            name: Pokemon's nickname or species name
            species_id: National Pokedex number
            level: Pokemon's level (1-100)
            nature: Pokemon's nature affecting stat growth
            base_stats: Base stats for the species
            evs: Effort Values (0-255 per stat, max 510 total)
            ivs: Individual Values (0-31 per stat)
            moves: List of move names (max 4)
            ability: Pokemon's ability
            status: Current status condition
            game_era: Game generation/era this Pokemon is from
        """
        # Validate basic parameters
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Name must be a non-empty string")
        
        if not isinstance(species_id, int) or species_id < 1 or species_id > 1008:
            raise ValueError("Species ID must be between 1 and 1008")
        
        if not isinstance(level, int) or level < 1 or level > 100:
            raise ValueError("Level must be between 1 and 100")
        
        if not isinstance(nature, PokemonNature):
            raise ValueError("Nature must be a valid PokemonNature enum value")
        
        if not isinstance(game_era, str) or not game_era.strip():
            raise ValueError("Game era must be a non-empty string")
        
        # Set basic properties
        self.name = name.strip()
        self.species_id = species_id
        self.level = level
        self.nature = nature
        self.game_era = game_era.strip()
        self.status = status
        self.is_shiny = is_shiny
        
        logger.debug(f"Created Pokemon: {self.name} (ID: {self.species_id}, Level: {self.level})")
        
        # Set stats with validation
        self.base_stats = base_stats or PokemonStats()
        self.evs = evs or PokemonEV()
        self.ivs = ivs or PokemonIV()
        
        # Validate and set moves
        if moves is None:
            moves = []
        if not isinstance(moves, list):
            raise ValueError("Moves must be a list")
        if len(moves) > 4:
            raise ValueError("Pokemon cannot have more than 4 moves")
        self.moves = moves[:4]  # Ensure max 4 moves
        
        # Set ability
        self.ability = ability
        
        # Set Pokemon types (simplified - in real implementation this would come from species data)
        self.types = self._determine_types()
        
        # Calculate actual stats based on level, EVs, IVs, and nature
        self._calculate_stats()
    
    def _calculate_stats(self):
        """Calculate actual Pokemon stats based on level, EVs, IVs, and nature."""
        # This is a simplified calculation - real Pokemon games have more complex formulas
        self.stats = PokemonStats()
        
        # Apply nature modifiers
        nature_modifiers = self._get_nature_modifiers()
        
        for stat_name in ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']:
            base_stat = getattr(self.base_stats, stat_name)
            ev = getattr(self.evs, stat_name)
            iv = getattr(self.ivs, stat_name)
            
            # Basic stat formula (simplified)
            if stat_name == 'hp':
                stat_value = int(((2 * base_stat + iv + ev // 4) * self.level) // 100 + self.level + 10)
            else:
                stat_value = int(((2 * base_stat + iv + ev // 4) * self.level) // 100 + 5)
            
            # Apply nature modifier
            if stat_name in nature_modifiers:
                stat_value = int(stat_value * nature_modifiers[stat_name])
            
            setattr(self.stats, stat_name, stat_value)
    
    def _get_nature_modifiers(self) -> Dict[str, float]:
        """Get stat modifiers for the Pokemon's nature."""
        # Each nature boosts one stat by 10% and reduces another by 10%.
        # Neutral natures (HARDY, DOCILE, SERIOUS, BASHFUL, QUIRKY) have no effect.
        NATURE_TABLE = {
            PokemonNature.LONELY:   ('attack',         'defense'),
            PokemonNature.BRAVE:    ('attack',         'speed'),
            PokemonNature.ADAMANT:  ('attack',         'special_attack'),
            PokemonNature.NAUGHTY:  ('attack',         'special_defense'),
            PokemonNature.BOLD:     ('defense',        'attack'),
            PokemonNature.RELAXED:  ('defense',        'speed'),
            PokemonNature.IMPISH:   ('defense',        'special_attack'),
            PokemonNature.LAX:      ('defense',        'special_defense'),
            PokemonNature.MODEST:   ('special_attack', 'attack'),
            PokemonNature.MILD:     ('special_attack', 'defense'),
            PokemonNature.QUIET:    ('special_attack', 'speed'),
            PokemonNature.RASH:     ('special_attack', 'special_defense'),
            PokemonNature.CALM:     ('special_defense', 'attack'),
            PokemonNature.GENTLE:   ('special_defense', 'defense'),
            PokemonNature.SASSY:    ('special_defense', 'speed'),
            PokemonNature.CAREFUL:  ('special_defense', 'special_attack'),
            PokemonNature.TIMID:    ('speed',           'attack'),
            PokemonNature.HASTY:    ('speed',           'defense'),
            PokemonNature.JOLLY:    ('speed',           'special_attack'),
            PokemonNature.NAIVE:    ('speed',           'special_defense'),
        }
        nature_modifiers = {
            'attack': 1.0, 'defense': 1.0, 'special_attack': 1.0,
            'special_defense': 1.0, 'speed': 1.0
        }
        if self.nature in NATURE_TABLE:
            boosted, reduced = NATURE_TABLE[self.nature]
            nature_modifiers[boosted] = 1.1
            nature_modifiers[reduced] = 0.9
        return nature_modifiers
    
    def add_move(self, move_name: str) -> bool:
        """Add a move to the Pokemon if there's space."""
        if not isinstance(move_name, str) or not move_name.strip():
            raise ValueError("Move name must be a non-empty string")
        
        if len(self.moves) >= 4:
            return False  # No space for more moves
        
        if move_name.strip() not in self.moves:
            self.moves.append(move_name.strip())
            return True
        
        return False  # Move already exists
    
    def remove_move(self, move_name: str) -> bool:
        """Remove a move from the Pokemon."""
        if move_name in self.moves:
            self.moves.remove(move_name)
            return True
        return False
    
    def is_legal(self) -> bool:
        """Check if the Pokemon has legal stats and moves for its game era."""
        # Basic legality checks
        if self.level < 1 or self.level > 100:
            return False
        
        # Check EV total
        total_evs = sum(self.evs.__dict__.values())
        if total_evs > 510:
            return False
        
        # Check individual EV limits
        for ev_value in self.evs.__dict__.values():
            if ev_value > 255:
                return False
        
        # Check IV limits
        for iv_value in self.ivs.__dict__.values():
            if iv_value > 31:
                return False
        
        # Check move count
        if len(self.moves) > 4:
            return False
        
        return True
    
    def _determine_types(self) -> List['PokemonType']:
        """Determine Pokemon types based on species ID using database."""
        from ..config.game_config import DatabaseConfig, GameConfig
        import json
        
        # Initialize database if needed
        if not GameConfig.POKEMON_DATABASE.exists():
            DatabaseConfig.initialize_databases()
        
        try:
            with open(GameConfig.POKEMON_DATABASE, 'r') as f:
                pokemon_data = json.load(f)
            
            if str(self.species_id) in pokemon_data:
                from .types import PokemonType
                type_names = pokemon_data[str(self.species_id)]['types']
                return [PokemonType(type_name.upper()) for type_name in type_names]
        except Exception as e:
            logger.warning(f"Could not load types for Pokemon {self.species_id}: {e}")
        
        # Fallback to simplified mapping
        from .types import PokemonType
        type_mapping = {
            1: [PokemonType.GRASS, PokemonType.POISON],      # Bulbasaur
            4: [PokemonType.FIRE],                           # Charmander
            7: [PokemonType.WATER],                          # Squirtle
            25: [PokemonType.ELECTRIC],                      # Pikachu
            133: [PokemonType.NORMAL],                       # Eevee
            150: [PokemonType.PSYCHIC],                      # Mewtwo
            151: [PokemonType.PSYCHIC],                      # Mew
        }
        
        if self.species_id in type_mapping:
            return type_mapping[self.species_id]
        
        # Default to Normal type if species not found
        return [PokemonType.NORMAL]
    
    def get_type_effectiveness(self, attack_type: 'PokemonType') -> float:
        """Get type effectiveness of an attack type against this Pokemon."""
        from .types import TypeEffectiveness
        
        # Pass the actual PokemonType enums, not their string values
        effectiveness, _ = TypeEffectiveness.calculate_effectiveness(attack_type, self.types)
        return effectiveness
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Pokemon to dictionary for serialization."""
        return {
            'name': self.name,
            'species_id': self.species_id,
            'level': self.level,
            'nature': self.nature.value,
            'base_stats': {
                'hp': self.base_stats.hp,
                'attack': self.base_stats.attack,
                'defense': self.base_stats.defense,
                'special_attack': self.base_stats.special_attack,
                'special_defense': self.base_stats.special_defense,
                'speed': self.base_stats.speed
            },
            'evs': {
                'hp': self.evs.hp,
                'attack': self.evs.attack,
                'defense': self.evs.defense,
                'special_attack': self.evs.special_attack,
                'special_defense': self.evs.special_defense,
                'speed': self.evs.speed
            },
            'ivs': {
                'hp': self.ivs.hp,
                'attack': self.ivs.attack,
                'defense': self.ivs.defense,
                'special_attack': self.ivs.special_attack,
                'special_defense': self.ivs.special_defense,
                'speed': self.ivs.speed
            },
            'moves': self.moves,
            'ability': self.ability,
            'status': self.status.value,
            'game_era': self.game_era,
            'calculated_stats': {
                'hp': self.stats.hp,
                'attack': self.stats.attack,
                'defense': self.stats.defense,
                'special_attack': self.stats.special_attack,
                'special_defense': self.stats.special_defense,
                'speed': self.stats.speed
            }
        }
    
    def __str__(self) -> str:
        """String representation of the Pokemon."""
        return f"{self.name} (Lv.{self.level}) - {self.nature.value} Nature"
    
    def __repr__(self) -> str:
        """Detailed representation of the Pokemon."""
        return f"Pokemon(name='{self.name}', species_id={self.species_id}, level={self.level}, nature={self.nature.value})"


class ShadowPokemon(Pokemon):
    """Special Pokemon class for GameCube era Shadow Pokemon mechanics."""
    
    def __init__(
        self,
        name: str,
        species_id: int,
        level: int = 1,
        nature: PokemonNature = PokemonNature.HARDY,
        base_stats: Optional[PokemonStats] = None,
        evs: Optional[PokemonEV] = None,
        ivs: Optional[PokemonIV] = None,
        moves: Optional[List[str]] = None,
        ability: Optional[str] = None,
        shadow_level: int = 1,
        purification_progress: float = 0.0
    ):
        """
        Initialize a Shadow Pokemon with purification mechanics.
        
        Args:
            shadow_level: Level of shadow corruption (1-5)
            purification_progress: Progress toward purification (0.0-1.0)
        """
        # Validate shadow-specific parameters
        if not isinstance(shadow_level, int) or shadow_level < 1 or shadow_level > 5:
            raise ValueError("Shadow level must be between 1 and 5")
        
        if not isinstance(purification_progress, float) or purification_progress < 0.0 or purification_progress > 1.0:
            raise ValueError("Purification progress must be between 0.0 and 1.0")
        
        # Initialize base Pokemon
        super().__init__(
            name=name,
            species_id=species_id,
            level=level,
            nature=nature,
            base_stats=base_stats,
            evs=evs,
            ivs=ivs,
            moves=moves,
            ability=ability,
            status=PokemonStatus.SHADOW,
            game_era="gamecube"
        )
        
        # Set shadow-specific properties
        self.shadow_level = shadow_level
        self.purification_progress = purification_progress
        
        # Apply shadow status effects
        self._apply_shadow_effects()
    
    def _apply_shadow_effects(self):
        """Apply shadow status effects to the Pokemon's stats."""
        # Shadow Pokemon have reduced stats based on shadow level
        shadow_multiplier = 1.0 - (self.shadow_level * 0.1)  # 10% reduction per shadow level
        
        for stat_name in ['attack', 'defense', 'special_attack', 'special_defense', 'speed']:
            current_stat = getattr(self.stats, stat_name)
            reduced_stat = int(current_stat * shadow_multiplier)
            setattr(self.stats, stat_name, reduced_stat)
    
    def purify(self, progress_increase: float = 0.1) -> bool:
        """
        Increase purification progress.
        
        Args:
            progress_increase: Amount to increase purification progress
            
        Returns:
            True if Pokemon is fully purified, False otherwise
        """
        if not isinstance(progress_increase, float) or progress_increase <= 0.0:
            raise ValueError("Progress increase must be a positive float")
        
        self.purification_progress = min(1.0, self.purification_progress + progress_increase)
        
        # Check if fully purified
        if self.purification_progress >= 1.0:
            self.status = PokemonStatus.NORMAL
            self._remove_shadow_effects()
            return True
        
        return False
    
    def _remove_shadow_effects(self):
        """Remove shadow status effects and restore normal stats."""
        # Recalculate stats without shadow effects
        self._calculate_stats()
    
    def get_shadow_moves(self) -> List[str]:
        """Get list of shadow moves available to this Pokemon."""
        # Shadow Pokemon have access to special shadow moves
        # This is a simplified implementation
        shadow_moves = [
            "Shadow Rush", "Shadow Blast", "Shadow Blitz", "Shadow Break",
            "Shadow Wave", "Shadow Storm", "Shadow Fire", "Shadow Chill",
            "Shadow Bolt", "Shadow Down", "Shadow Half", "Shadow Hold",
            "Shadow Mist", "Shadow Panic", "Shadow Rage", "Shadow Shed"
        ]
        
        # Return moves appropriate for the Pokemon's level and shadow level
        available_moves = shadow_moves[:self.shadow_level + 1]
        return available_moves
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Shadow Pokemon to dictionary for serialization."""
        base_dict = super().to_dict()
        base_dict.update({
            'shadow_level': self.shadow_level,
            'purification_progress': self.purification_progress,
            'is_shadow': True
        })
        return base_dict
    
    def __str__(self) -> str:
        """String representation of the Shadow Pokemon."""
        return f"{self.name} (Lv.{self.level}) - Shadow Lv.{self.shadow_level} - {self.purification_progress:.1%} Purified"
    
    def __repr__(self) -> str:
        """Detailed representation of the Shadow Pokemon."""
        return f"ShadowPokemon(name='{self.name}', species_id={self.species_id}, level={self.level}, shadow_level={self.shadow_level})"
