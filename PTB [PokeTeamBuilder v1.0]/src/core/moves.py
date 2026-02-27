"""
Pokemon moves system with comprehensive validation and game era support.
Includes special mechanics for different generations and game types.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import json


class MoveCategory(Enum):
    """Move categories affecting damage calculation."""
    PHYSICAL = "physical"
    SPECIAL = "special"
    STATUS = "status"


class MoveTarget(Enum):
    """Move targeting system."""
    SINGLE_OPPONENT = "single_opponent"
    ALL_OPPONENTS = "all_opponents"
    SINGLE_ALLY = "single_ally"
    ALL_ALLIES = "all_allies"
    SELF = "self"
    ALL_POKEMON = "all_pokemon"
    RANDOM_OPPONENT = "random_opponent"
    OPPONENTS_FIELD = "opponents_field"
    ALLIES_FIELD = "allies_field"
    ENTIRE_FIELD = "entire_field"


class MoveType(Enum):
    """Pokemon types for moves."""
    NORMAL = "normal"
    FIRE = "fire"
    WATER = "water"
    ELECTRIC = "electric"
    GRASS = "grass"
    ICE = "ice"
    FIGHTING = "fighting"
    POISON = "poison"
    GROUND = "ground"
    FLYING = "flying"
    PSYCHIC = "psychic"
    BUG = "bug"
    ROCK = "rock"
    GHOST = "ghost"
    DRAGON = "dragon"
    DARK = "dark"
    STEEL = "steel"
    FAIRY = "fairy"
    SHADOW = "shadow"  # GameCube era specific


@dataclass
class MoveEffect:
    """Move effects and side effects."""
    effect_type: str
    effect_chance: float = 0.0
    effect_value: int = 0
    effect_description: str = ""
    
    def __post_init__(self):
        """Validate effect parameters."""
        if not isinstance(self.effect_type, str) or not self.effect_type.strip():
            raise ValueError("Effect type must be a non-empty string")
        
        if not isinstance(self.effect_chance, float) or self.effect_chance < 0.0 or self.effect_chance > 1.0:
            raise ValueError("Effect chance must be between 0.0 and 1.0")
        
        if not isinstance(self.effect_value, int):
            raise ValueError("Effect value must be an integer")


class Move:
    """Comprehensive Pokemon move class with validation."""
    
    def __init__(
        self,
        name: str,
        move_type: MoveType,
        category: MoveCategory,
        power: int,
        accuracy: int,
        pp: int,
        description: str = "",
        target: MoveTarget = MoveTarget.SINGLE_OPPONENT,
        priority: int = 0,
        effects: Optional[List[MoveEffect]] = None,
        game_era: str = "modern",
        is_shadow_move: bool = False
    ):
        """
        Initialize a Pokemon move with comprehensive validation.
        
        Args:
            name: Move name
            move_type: Type of the move (affects effectiveness)
            category: Physical, Special, or Status
            power: Base power (0 for status moves)
            accuracy: Accuracy percentage (0-100, 0 for always hits)
            pp: Power Points (uses per battle)
            description: Move description
            target: What the move targets
            priority: Move priority (-7 to +5)
            effects: List of move effects
            game_era: Game generation this move is from
            is_shadow_move: Whether this is a GameCube era shadow move
        """
        # Validate basic parameters
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Move name must be a non-empty string")
        
        if not isinstance(move_type, MoveType):
            raise ValueError("Move type must be a valid MoveType enum value")
        
        if not isinstance(category, MoveCategory):
            raise ValueError("Move category must be a valid MoveCategory enum value")
        
        if not isinstance(power, int) or power < 0:
            raise ValueError("Power must be a non-negative integer")
        
        if not isinstance(accuracy, int) or accuracy < 0 or accuracy > 100:
            raise ValueError("Accuracy must be between 0 and 100")
        
        if not isinstance(pp, int) or pp < 1 or pp > 40:
            raise ValueError("PP must be between 1 and 40")
        
        if not isinstance(priority, int) or priority < -7 or priority > 5:
            raise ValueError("Priority must be between -7 and 5")
        
        if not isinstance(game_era, str) or not game_era.strip():
            raise ValueError("Game era must be a non-empty string")
        
        if not isinstance(is_shadow_move, bool):
            raise ValueError("is_shadow_move must be a boolean")
        
        # Set basic properties
        self.name = name.strip()
        self.move_type = move_type
        self.category = category
        self.power = power
        self.accuracy = accuracy
        self.pp = pp
        self.description = description.strip()
        self.target = target
        self.priority = priority
        self.game_era = game_era.strip()
        self.is_shadow_move = is_shadow_move
        
        # Set effects with validation
        if effects is None:
            effects = []
        if not isinstance(effects, list):
            raise ValueError("Effects must be a list")
        
        # Validate each effect
        for effect in effects:
            if not isinstance(effect, MoveEffect):
                raise ValueError("Each effect must be a MoveEffect instance")
        
        self.effects = effects
        
        # Validate move consistency
        self._validate_move_consistency()
    
    def _validate_move_consistency(self):
        """Validate move parameters for consistency."""
        # Status moves should have 0 power
        if self.category == MoveCategory.STATUS and self.power != 0:
            raise ValueError("Status moves must have 0 power")
        
        # Physical and Special moves should have power > 0
        if self.category in [MoveCategory.PHYSICAL, MoveCategory.SPECIAL] and self.power == 0:
            raise ValueError("Physical and Special moves must have power > 0")
        
        # Shadow moves should be from GameCube era
        if self.is_shadow_move and self.game_era != "gamecube":
            raise ValueError("Shadow moves must be from GameCube era")
    
    def calculate_damage(
        self,
        attacker_level: int,
        attacker_attack: int,
        defender_defense: int,
        type_effectiveness: float = 1.0,
        critical_hit: bool = False,
        stab_bonus: bool = False,
        weather_modifier: float = 1.0,
        other_modifiers: float = 1.0
    ) -> int:
        """
        Calculate move damage using Pokemon battle formulas.
        
        Args:
            attacker_level: Attacking Pokemon's level
            attacker_attack: Attacking Pokemon's relevant attack stat
            defender_defense: Defending Pokemon's relevant defense stat
            type_effectiveness: Type effectiveness multiplier
            critical_hit: Whether the move is a critical hit
            stab_bonus: Same Type Attack Bonus
            weather_modifier: Weather-based damage modifier
            other_modifiers: Other damage modifiers
            
        Returns:
            Calculated damage value
        """
        if self.category == MoveCategory.STATUS:
            return 0
        
        # Base damage formula
        if self.category == MoveCategory.PHYSICAL:
            attack_stat = attacker_attack
            defense_stat = defender_defense
        else:  # Special
            # For special moves, we'd need special attack/defense stats
            # This is simplified for now
            attack_stat = attacker_attack
            defense_stat = defender_defense
        
        # Basic damage formula
        damage = int(((2 * attacker_level / 5 + 2) * self.power * attack_stat / defense_stat) / 50 + 2)
        
        # Apply modifiers
        damage = int(damage * type_effectiveness)
        
        if critical_hit:
            damage = int(damage * 1.5)
        
        if stab_bonus:
            damage = int(damage * 1.5)
        
        damage = int(damage * weather_modifier)
        damage = int(damage * other_modifiers)
        
        # Ensure minimum damage of 1
        return max(1, damage)
    
    def get_effectiveness_against(self, target_types: List[MoveType]) -> float:
        """
        Calculate type effectiveness against target Pokemon types.
        
        Args:
            target_types: List of target Pokemon's types
            
        Returns:
            Effectiveness multiplier
        """
        if not target_types:
            return 1.0
        
        # Type effectiveness chart (simplified)
        effectiveness_chart = {
            MoveType.NORMAL: {MoveType.ROCK: 0.5, MoveType.GHOST: 0.0, MoveType.STEEL: 0.5},
            MoveType.FIRE: {MoveType.FIRE: 0.5, MoveType.WATER: 0.5, MoveType.GRASS: 2.0, MoveType.ICE: 2.0, MoveType.BUG: 2.0, MoveType.ROCK: 0.5, MoveType.DRAGON: 0.5, MoveType.STEEL: 2.0},
            MoveType.WATER: {MoveType.FIRE: 2.0, MoveType.WATER: 0.5, MoveType.GRASS: 0.5, MoveType.GROUND: 2.0, MoveType.ROCK: 2.0, MoveType.DRAGON: 0.5},
            MoveType.ELECTRIC: {MoveType.WATER: 2.0, MoveType.ELECTRIC: 0.5, MoveType.GRASS: 0.5, MoveType.GROUND: 0.0, MoveType.FLYING: 2.0, MoveType.DRAGON: 0.5},
            MoveType.GRASS: {MoveType.FIRE: 0.5, MoveType.WATER: 2.0, MoveType.GRASS: 0.5, MoveType.POISON: 0.5, MoveType.GROUND: 2.0, MoveType.FLYING: 0.5, MoveType.BUG: 0.5, MoveType.ROCK: 2.0, MoveType.DRAGON: 0.5, MoveType.STEEL: 0.5},
            MoveType.ICE: {MoveType.FIRE: 0.5, MoveType.WATER: 0.5, MoveType.GRASS: 2.0, MoveType.ICE: 0.5, MoveType.GROUND: 2.0, MoveType.FLYING: 2.0, MoveType.DRAGON: 2.0, MoveType.STEEL: 0.5},
            MoveType.FIGHTING: {MoveType.NORMAL: 2.0, MoveType.ICE: 2.0, MoveType.POISON: 0.5, MoveType.GROUND: 0.5, MoveType.FLYING: 0.5, MoveType.PSYCHIC: 0.5, MoveType.BUG: 0.5, MoveType.ROCK: 2.0, MoveType.GHOST: 0.0, MoveType.STEEL: 2.0, MoveType.FAIRY: 0.5},
            MoveType.POISON: {MoveType.GRASS: 2.0, MoveType.POISON: 0.5, MoveType.GROUND: 0.5, MoveType.ROCK: 0.5, MoveType.GHOST: 0.5, MoveType.STEEL: 0.0, MoveType.FAIRY: 2.0},
            MoveType.GROUND: {MoveType.FIRE: 2.0, MoveType.ELECTRIC: 2.0, MoveType.GRASS: 0.5, MoveType.POISON: 2.0, MoveType.FLYING: 0.0, MoveType.BUG: 0.5, MoveType.ROCK: 2.0, MoveType.STEEL: 2.0},
            MoveType.FLYING: {MoveType.ELECTRIC: 0.5, MoveType.GRASS: 2.0, MoveType.FIGHTING: 2.0, MoveType.BUG: 2.0, MoveType.ROCK: 0.5, MoveType.STEEL: 0.5},
            MoveType.PSYCHIC: {MoveType.FIGHTING: 2.0, MoveType.POISON: 2.0, MoveType.PSYCHIC: 0.5, MoveType.DARK: 0.0, MoveType.STEEL: 0.5},
            MoveType.BUG: {MoveType.FIRE: 0.5, MoveType.GRASS: 2.0, MoveType.FIGHTING: 0.5, MoveType.POISON: 0.5, MoveType.FLYING: 0.5, MoveType.PSYCHIC: 2.0, MoveType.GHOST: 0.5, MoveType.STEEL: 0.5, MoveType.FAIRY: 0.5},
            MoveType.ROCK: {MoveType.FIRE: 2.0, MoveType.ICE: 2.0, MoveType.FIGHTING: 0.5, MoveType.GROUND: 0.5, MoveType.FLYING: 2.0, MoveType.BUG: 2.0, MoveType.STEEL: 0.5},
            MoveType.GHOST: {MoveType.NORMAL: 0.0, MoveType.PSYCHIC: 2.0, MoveType.GHOST: 2.0, MoveType.DARK: 0.5},
            MoveType.DRAGON: {MoveType.DRAGON: 2.0, MoveType.STEEL: 0.5, MoveType.FAIRY: 0.0},
            MoveType.DARK: {MoveType.FIGHTING: 0.5, MoveType.PSYCHIC: 2.0, MoveType.GHOST: 2.0, MoveType.DARK: 0.5, MoveType.FAIRY: 0.5},
            MoveType.STEEL: {MoveType.FIRE: 0.5, MoveType.WATER: 0.5, MoveType.ELECTRIC: 0.5, MoveType.ICE: 2.0, MoveType.ROCK: 2.0, MoveType.STEEL: 0.5, MoveType.FAIRY: 2.0},
            MoveType.FAIRY: {MoveType.FIGHTING: 2.0, MoveType.POISON: 0.5, MoveType.DRAGON: 2.0, MoveType.DARK: 2.0, MoveType.STEEL: 0.5},
            MoveType.SHADOW: {MoveType.NORMAL: 1.5, MoveType.PSYCHIC: 2.0, MoveType.GHOST: 1.5, MoveType.DARK: 0.5}  # GameCube era
        }
        
        total_effectiveness = 1.0
        
        for target_type in target_types:
            if self.move_type in effectiveness_chart and target_type in effectiveness_chart[self.move_type]:
                total_effectiveness *= effectiveness_chart[self.move_type][target_type]
        
        return total_effectiveness
    
    def is_legal_for_era(self, game_era: str) -> bool:
        """
        Check if this move is legal for the specified game era.
        
        Args:
            game_era: Target game era
            
        Returns:
            True if move is legal for the era
        """
        # Era-specific move legality
        era_restrictions = {
            "gamecube": ["shadow"],  # GameCube era
            "ds": ["gamecube", "shadow"],  # DS era includes GameCube
            "3ds": ["gamecube", "shadow", "ds"],  # 3DS era includes previous
            "switch": ["gamecube", "shadow", "ds", "3ds"]  # Switch era includes all
        }
        
        if game_era not in era_restrictions:
            return False
        
        # Check if move type is allowed in target era
        if self.move_type == MoveType.SHADOW and "shadow" not in era_restrictions[game_era]:
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert move to dictionary for serialization."""
        return {
            'name': self.name,
            'move_type': self.move_type.value,
            'category': self.category.value,
            'power': self.power,
            'accuracy': self.accuracy,
            'pp': self.pp,
            'description': self.description,
            'target': self.target.value,
            'priority': self.priority,
            'game_era': self.game_era,
            'is_shadow_move': self.is_shadow_move,
            'effects': [effect.__dict__ for effect in self.effects]
        }
    
    def __str__(self) -> str:
        """String representation of the move."""
        return f"{self.name} ({self.move_type.value}, {self.category.value}, Power: {self.power}, Acc: {self.accuracy}%)"
    
    def __repr__(self) -> str:
        """Detailed representation of the move."""
        return f"Move(name='{self.name}', type={self.move_type.value}, category={self.category.value}, power={self.power})"


# Predefined shadow moves for GameCube era
SHADOW_MOVES = {
    "Shadow Rush": Move(
        name="Shadow Rush",
        move_type=MoveType.SHADOW,
        category=MoveCategory.PHYSICAL,
        power=55,
        accuracy=100,
        pp=15,
        description="A shadow move that may cause flinching",
        is_shadow_move=True,
        game_era="gamecube"
    ),
    "Shadow Blast": Move(
        name="Shadow Blast",
        move_type=MoveType.SHADOW,
        category=MoveCategory.SPECIAL,
        power=80,
        accuracy=85,
        pp=10,
        description="A powerful shadow move",
        is_shadow_move=True,
        game_era="gamecube"
    ),
    "Shadow Wave": Move(
        name="Shadow Wave",
        move_type=MoveType.SHADOW,
        category=MoveCategory.SPECIAL,
        power=50,
        accuracy=90,
        pp=20,
        description="A shadow move that hits all opponents",
        target=MoveTarget.ALL_OPPONENTS,
        is_shadow_move=True,
        game_era="gamecube"
    )
}
