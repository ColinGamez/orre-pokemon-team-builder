"""
Team analysis and evaluation system.
Provides comprehensive analysis of Pokemon teams for competitive play.
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from ..core import Pokemon, ShadowPokemon, PokemonType, TypeEffectiveness, Move
from .team import PokemonTeam, TeamFormat, TeamEra


class AnalysisType(Enum):
    """Types of team analysis."""
    TYPE_COVERAGE = "type_coverage"
    WEAKNESS_ANALYSIS = "weakness_analysis"
    SYNERGY_ANALYSIS = "synergy_analysis"
    STAT_ANALYSIS = "stat_analysis"
    MOVE_COVERAGE = "move_coverage"
    ERA_COMPATIBILITY = "era_compatibility"


@dataclass
class TypeCoverage:
    """Type coverage analysis results."""
    offensive_coverage: Dict[str, List[str]]  # Type -> List of Pokemon names
    defensive_coverage: Dict[str, List[str]]  # Type -> List of Pokemon names
    coverage_score: float  # 0.0 to 1.0
    missing_types: List[str]  # Types not covered
    overcovered_types: List[str]  # Types covered by many Pokemon


@dataclass
class WeaknessAnalysis:
    """Team weakness analysis results."""
    team_weaknesses: Dict[str, List[str]]  # Type -> List of Pokemon names
    critical_weaknesses: List[str]  # Types that hit multiple Pokemon super effectively
    resistance_coverage: Dict[str, List[str]]  # Type -> List of Pokemon names
    immunity_coverage: Dict[str, List[str]]  # Type -> List of Pokemon names
    overall_defense_score: float  # 0.0 to 1.0


@dataclass
class SynergyAnalysis:
    """Team synergy analysis results."""
    core_synergies: List[Tuple[str, str, str]]  # (Pokemon1, Pokemon2, synergy_type)
    anti_synergies: List[Tuple[str, str, str]]  # (Pokemon1, Pokemon2, conflict_type)
    synergy_score: float  # 0.0 to 1.0
    recommendations: List[str]  # Improvement suggestions


@dataclass
class StatAnalysis:
    """Team stat analysis results."""
    stat_totals: Dict[str, int]  # Stat -> Total value
    stat_averages: Dict[str, float]  # Stat -> Average value
    stat_distribution: Dict[str, List[int]]  # Stat -> List of individual values
    balance_score: float  # 0.0 to 1.0
    specialized_roles: List[Tuple[str, str]]  # (Pokemon, role)


class TeamAnalyzer:
    """Comprehensive team analysis and evaluation system."""
    
    def __init__(self, team: PokemonTeam):
        """
        Initialize team analyzer.
        
        Args:
            team: Pokemon team to analyze
        """
        self.team = team
        self.active_pokemon = team.get_active_pokemon()
    
    def analyze_team(self) -> Dict[str, Any]:
        """
        Perform comprehensive team analysis.
        
        Returns:
            Dictionary containing all analysis results
        """
        return {
            'type_coverage': self.analyze_type_coverage(),
            'weakness_analysis': self.analyze_weaknesses(),
            'synergy_analysis': self.analyze_synergies(),
            'stat_analysis': self.analyze_stats(),
            'move_coverage': self.analyze_move_coverage(),
            'era_compatibility': self.analyze_era_compatibility(),
            'overall_score': self.calculate_overall_score()
        }
    
    def analyze_type_coverage(self) -> TypeCoverage:
        """Analyze offensive and defensive type coverage."""
        offensive_coverage = {}
        defensive_coverage = {}
        
        # Analyze offensive coverage (moves)
        for pokemon in self.active_pokemon:
            for move in pokemon.moves:
                # Handle both Move objects and string move names
                if hasattr(move, 'move_type'):
                    move_type = move.move_type.value
                else:
                    # For string moves, we'll use a simplified type mapping
                    move_type = self._get_move_type_from_name(move)
                
                if move_type not in offensive_coverage:
                    offensive_coverage[move_type] = []
                offensive_coverage[move_type].append(pokemon.name)
        
        # Analyze defensive coverage (Pokemon types)
        for pokemon in self.active_pokemon:
            for pokemon_type in pokemon.types:
                type_name = pokemon_type.value
                if type_name not in defensive_coverage:
                    defensive_coverage[type_name] = []
                defensive_coverage[type_name].append(pokemon.name)
        
        # Calculate coverage score
        all_types = [t.value for t in PokemonType]
        covered_offensive = len(offensive_coverage)
        covered_defensive = len(defensive_coverage)
        
        offensive_score = covered_offensive / len(all_types)
        defensive_score = covered_defensive / len(all_types)
        coverage_score = (offensive_score + defensive_score) / 2
        
        # Find missing and overcovered types
        missing_offensive = [t for t in all_types if t not in offensive_coverage]
        missing_defensive = [t for t in all_types if t not in defensive_coverage]
        missing_types = list(set(missing_offensive + missing_defensive))
        
        overcovered_types = []
        for type_name, pokemon_list in offensive_coverage.items():
            if len(pokemon_list) > 2:  # More than 2 Pokemon have this type move
                overcovered_types.append(type_name)
        
        return TypeCoverage(
            offensive_coverage=offensive_coverage,
            defensive_coverage=defensive_coverage,
            coverage_score=coverage_score,
            missing_types=missing_types,
            overcovered_types=overcovered_types
        )
    
    def analyze_weaknesses(self) -> WeaknessAnalysis:
        """Analyze team weaknesses and resistances."""
        team_weaknesses = {}
        resistance_coverage = {}
        immunity_coverage = {}
        
        # Analyze each Pokemon's weaknesses
        for pokemon in self.active_pokemon:
            pokemon_types = [t.value for t in pokemon.types]
            
            # Check against all types
            for attack_type in PokemonType:
                # Convert string types to PokemonType enum values for the calculation
                pokemon_type_enums = []
                for type_name in pokemon_types:
                    try:
                        type_enum = PokemonType(type_name)
                        pokemon_type_enums.append(type_enum)
                    except ValueError:
                        # Skip invalid type names
                        continue
                
                if pokemon_type_enums:
                    effectiveness, _ = TypeEffectiveness.calculate_effectiveness(
                        attack_type, pokemon_type_enums
                    )
                    
                    if effectiveness > 1.0:  # Super effective
                        type_name = attack_type.value
                        if type_name not in team_weaknesses:
                            team_weaknesses[type_name] = []
                        team_weaknesses[type_name].append(pokemon.name)
                    
                    elif effectiveness < 1.0:  # Resistant
                        type_name = attack_type.value
                        if type_name not in resistance_coverage:
                            resistance_coverage[type_name] = []
                        resistance_coverage[type_name].append(pokemon.name)
                    
                    elif effectiveness == 0.0:  # Immune
                        type_name = attack_type.value
                        if type_name not in immunity_coverage:
                            immunity_coverage[type_name] = []
                        immunity_coverage[type_name].append(pokemon.name)
        
        # Find critical weaknesses (hit multiple Pokemon)
        critical_weaknesses = [
            type_name for type_name, pokemon_list in team_weaknesses.items()
            if len(pokemon_list) >= 2
        ]
        
        # Calculate overall defense score
        total_vulnerabilities = sum(len(pokemon_list) for pokemon_list in team_weaknesses.values())
        total_resistances = sum(len(pokemon_list) for pokemon_list in resistance_coverage.values())
        total_immunities = sum(len(pokemon_list) for pokemon_list in immunity_coverage.values())
        
        if total_vulnerabilities == 0:
            overall_defense_score = 1.0
        else:
            defense_score = (total_resistances + total_immunities * 2) / (total_vulnerabilities + total_resistances + total_immunities)
            overall_defense_score = max(0.0, min(1.0, defense_score))
        
        return WeaknessAnalysis(
            team_weaknesses=team_weaknesses,
            critical_weaknesses=critical_weaknesses,
            resistance_coverage=resistance_coverage,
            immunity_coverage=immunity_coverage,
            overall_defense_score=overall_defense_score
        )
    
    def analyze_synergies(self) -> SynergyAnalysis:
        """Analyze team synergies and conflicts."""
        core_synergies = []
        anti_synergies = []
        
        # Analyze Pokemon pairs
        for i, pokemon1 in enumerate(self.active_pokemon):
            for j, pokemon2 in enumerate(self.active_pokemon[i+1:], i+1):
                synergy_type, conflict_type = self._analyze_pokemon_pair(pokemon1, pokemon2)
                
                if synergy_type:
                    core_synergies.append((pokemon1.name, pokemon2.name, synergy_type))
                
                if conflict_type:
                    anti_synergies.append((pokemon1.name, pokemon2.name, conflict_type))
        
        # Calculate synergy score
        total_pairs = len(self.active_pokemon) * (len(self.active_pokemon) - 1) // 2
        if total_pairs == 0:
            synergy_score = 1.0
        else:
            positive_synergies = len(core_synergies)
            negative_synergies = len(anti_synergies)
            synergy_score = max(0.0, min(1.0, positive_synergies / total_pairs))
        
        # Generate recommendations
        recommendations = self._generate_synergy_recommendations(core_synergies, anti_synergies)
        
        return SynergyAnalysis(
            core_synergies=core_synergies,
            anti_synergies=anti_synergies,
            synergy_score=synergy_score,
            recommendations=recommendations
        )
    
    def analyze_stats(self) -> StatAnalysis:
        """Analyze team stat distribution and balance."""
        if not self.active_pokemon:
            return StatAnalysis(
                stat_totals={},
                stat_averages={},
                stat_distribution={},
                balance_score=0.0,
                specialized_roles=[]
            )
        
        # Collect all stats
        stat_names = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']
        stat_totals = {stat: 0 for stat in stat_names}
        stat_distribution = {stat: [] for stat in stat_names}
        
        for pokemon in self.active_pokemon:
            pokemon_stats = pokemon.stats.get_all_stats()
            for stat_name in stat_names:
                if stat_name in pokemon_stats:
                    stat_value = pokemon_stats[stat_name]
                    stat_totals[stat_name] += stat_value
                    stat_distribution[stat_name].append(stat_value)
        
        # Calculate averages
        team_size = len(self.active_pokemon)
        stat_averages = {stat: total / team_size for stat, total in stat_totals.items()}
        
        # Calculate balance score
        balance_score = self._calculate_stat_balance(stat_distribution)
        
        # Identify specialized roles
        specialized_roles = self._identify_specialized_roles(stat_averages, stat_distribution)
        
        return StatAnalysis(
            stat_totals=stat_totals,
            stat_averages=stat_averages,
            stat_distribution=stat_distribution,
            balance_score=balance_score,
            specialized_roles=specialized_roles
        )
    
    def analyze_move_coverage(self) -> Dict[str, Any]:
        """Analyze move coverage and variety."""
        move_types = {}
        move_categories = {}
        priority_moves = []
        status_moves = []
        
        for pokemon in self.active_pokemon:
            for move in pokemon.moves:
                # Handle both Move objects and string move names
                if hasattr(move, 'move_type'):
                    move_type = move.move_type.value
                    move_category = move.category.value
                    move_priority = move.priority
                    is_status = move.category.value == "status"
                else:
                    # For string moves, use simplified analysis
                    move_type = self._get_move_type_from_name(move)
                    move_category = self._get_move_category_from_name(move)
                    move_priority = 0  # Default priority
                    is_status = move_category == "status"
                
                # Move types
                if move_type not in move_types:
                    move_types[move_type] = []
                move_types[move_type].append(f"{pokemon.name}: {move}")
                
                # Move categories
                if move_category not in move_categories:
                    move_categories[move_category] = []
                move_categories[move_category].append(f"{pokemon.name}: {move}")
                
                # Priority moves
                if move_priority > 0:
                    priority_moves.append(f"{pokemon.name}: {move} (+{move_priority})")
                
                # Status moves
                if is_status:
                    status_moves.append(f"{pokemon.name}: {move}")
        
        return {
            'move_types': move_types,
            'move_categories': move_categories,
            'priority_moves': priority_moves,
            'status_moves': status_moves,
            'total_moves': sum(len(pokemon.moves) for pokemon in self.active_pokemon)
        }
    
    def analyze_era_compatibility(self) -> Dict[str, Any]:
        """Analyze team compatibility with target game era."""
        compatibility_issues = []
        era_specific_features = []
        
        for pokemon in self.active_pokemon:
            # Check Pokemon era compatibility
            if hasattr(pokemon, 'shadow_level') and pokemon.shadow_level > 0:
                if self.team.era not in [TeamEra.GAMECUBE, TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
                    compatibility_issues.append(f"{pokemon.name} is a Shadow Pokemon (GameCube era only)")
                else:
                    era_specific_features.append(f"{pokemon.name} uses Shadow mechanics")
            
            # Check move era compatibility
            for move in pokemon.moves:
                # Handle both Move objects and string move names
                if hasattr(move, 'is_shadow_move'):
                    # Move object
                    move_name = move.name
                    is_shadow_move = move.is_shadow_move
                else:
                    # String move name
                    move_name = move
                    is_shadow_move = 'shadow' in move_name.lower()
                
                if is_shadow_move and self.team.era not in [TeamEra.GAMECUBE, TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
                    compatibility_issues.append(f"{pokemon.name} has Shadow move {move_name} (GameCube era only)")
                elif is_shadow_move:
                    era_specific_features.append(f"{pokemon.name} uses Shadow move {move_name}")
        
        return {
            'compatibility_issues': compatibility_issues,
            'era_specific_features': era_specific_features,
            'is_fully_compatible': len(compatibility_issues) == 0
        }
    
    def calculate_overall_score(self) -> float:
        """Calculate overall team quality score."""
        type_coverage = self.analyze_type_coverage()
        weakness_analysis = self.analyze_weaknesses()
        synergy_analysis = self.analyze_synergies()
        stat_analysis = self.analyze_stats()
        era_compatibility = self.analyze_era_compatibility()
        
        # Weighted scoring
        scores = {
            'type_coverage': type_coverage.coverage_score * 0.25,
            'defense': weakness_analysis.overall_defense_score * 0.25,
            'synergy': synergy_analysis.synergy_score * 0.20,
            'stats': stat_analysis.balance_score * 0.20,
            'compatibility': 1.0 if era_compatibility['is_fully_compatible'] else 0.5
        }
        
        overall_score = sum(scores.values()) / len(scores)
        return round(overall_score, 3)
    
    def _analyze_pokemon_pair(self, pokemon1: Pokemon, pokemon2: Pokemon) -> Tuple[Optional[str], Optional[str]]:
        """Analyze synergy between two Pokemon."""
        synergy_type = None
        conflict_type = None
        
        # Type synergy analysis
        types1 = [t.value for t in pokemon1.types]
        types2 = [t.value for t in pokemon2.types]
        
        # Check for type synergy (one resists what the other is weak to)
        for type1 in types1:
            for type2 in types2:
                # Check if pokemon2 resists pokemon1's weaknesses
                if self._has_type_advantage(type2, type1):
                    synergy_type = f"Type coverage: {pokemon2.name} covers {pokemon1.name}'s {type1} weakness"
                    break
        
        # Check for conflicts (both weak to same type)
        for type1 in types1:
            for type2 in types2:
                if type1 == type2:
                    # Both Pokemon share a type, check if this creates a shared weakness
                    shared_weaknesses = self._get_type_weaknesses(type1)
                    if shared_weaknesses:
                        conflict_type = f"Shared weakness: Both weak to {', '.join(shared_weaknesses)}"
                        break
        
        return synergy_type, conflict_type
    
    def _has_type_advantage(self, defending_type: str, attacking_type: str) -> bool:
        """Check if defending type resists the attacking type using the canonical type chart."""
        try:
            atk = PokemonType(attacking_type)
            dfn = PokemonType(defending_type)
            effectiveness, _ = TypeEffectiveness.calculate_effectiveness(atk, [dfn])
            return effectiveness > 1.0
        except ValueError:
            return False

    def _get_type_weaknesses(self, pokemon_type: str) -> List[str]:
        """Get weaknesses for a given type using the canonical type chart."""
        try:
            dfn = PokemonType(pokemon_type)
            weaknesses = TypeEffectiveness.get_weaknesses([dfn])
            return [t.value for t in weaknesses.keys()]
        except ValueError:
            return []

    def _calculate_stat_balance(self, stat_distribution: Dict[str, List[int]]) -> float:
        """Calculate how balanced the team's stats are."""
        if not stat_distribution:
            return 0.0
        
        # Calculate coefficient of variation for each stat
        cv_scores = []
        for stat_name, values in stat_distribution.items():
            if len(values) > 1:
                mean = sum(values) / len(values)
                variance = sum((x - mean) ** 2 for x in values) / len(values)
                std_dev = variance ** 0.5
                cv = std_dev / mean if mean > 0 else 0
                cv_scores.append(cv)
        
        if not cv_scores:
            return 1.0
        
        # Lower CV means more balanced stats
        avg_cv = sum(cv_scores) / len(cv_scores)
        balance_score = max(0.0, min(1.0, 1.0 - avg_cv))
        return balance_score
    
    def _identify_specialized_roles(self, stat_averages: Dict[str, float], stat_distribution: Dict[str, List[int]]) -> List[Tuple[str, str]]:
        """Identify specialized roles for each Pokemon."""
        if not self.active_pokemon:
            return []
        
        specialized_roles = []
        
        for pokemon in self.active_pokemon:
            pokemon_stats = pokemon.stats.get_all_stats()
            role = self._determine_pokemon_role(pokemon_stats, stat_averages)
            specialized_roles.append((pokemon.name, role))
        
        return specialized_roles
    
    def _determine_pokemon_role(self, pokemon_stats: Dict[str, int], team_averages: Dict[str, float]) -> str:
        """Determine the role of a Pokemon based on its stats."""
        if not pokemon_stats or not team_averages:
            return "Balanced"
        
        # Calculate how much each stat deviates from team average
        deviations = {}
        for stat_name, stat_value in pokemon_stats.items():
            if stat_name in team_averages:
                avg_value = team_averages[stat_name]
                if avg_value > 0:
                    deviation = (stat_value - avg_value) / avg_value
                    deviations[stat_name] = deviation
        
        if not deviations:
            return "Balanced"
        
        # Find the stat with highest positive deviation
        max_deviation = max(deviations.values())
        if max_deviation > 0.2:  # 20% above average
            for stat_name, dev in deviations.items():
                if dev == max_deviation:
                    if stat_name in ['attack', 'special_attack']:
                        return "Attacker"
                    elif stat_name in ['defense', 'special_defense']:
                        return "Defender"
                    elif stat_name == 'speed':
                        return "Speedster"
                    elif stat_name == 'hp':
                        return "Tank"
        
        return "Balanced"
    
    def _generate_synergy_recommendations(self, synergies: List[Tuple[str, str, str]], anti_synergies: List[Tuple[str, str, str]]) -> List[str]:
        """Generate recommendations based on synergy analysis."""
        recommendations = []
        
        if len(synergies) < len(self.active_pokemon) // 2:
            recommendations.append("Consider adding Pokemon that cover your team's weaknesses")
        
        if anti_synergies:
            recommendations.append("Address shared weaknesses between Pokemon")
        
        if len(synergies) > len(anti_synergies) * 2:
            recommendations.append("Good team synergy! Consider maintaining this balance")
        
        return recommendations
    
    def _get_move_type_from_name(self, move_name: str) -> str:
        """Get move type from move name (simplified implementation)."""
        # Simplified move type mapping - in a real implementation this would come from a database
        move_type_mapping = {
            # Fire moves
            'fire blast': 'fire', 'flamethrower': 'fire', 'ember': 'fire', 'fire punch': 'fire',
            # Water moves
            'surf': 'water', 'hydro pump': 'water', 'water gun': 'water', 'aqua jet': 'water',
            # Grass moves
            'vine whip': 'grass', 'solar beam': 'grass', 'razor leaf': 'grass', 'seed bomb': 'grass',
            # Electric moves
            'thunderbolt': 'electric', 'thunder': 'electric', 'spark': 'electric', 'volt tackle': 'electric',
            # Ice moves
            'ice beam': 'ice', 'blizzard': 'ice', 'ice punch': 'ice', 'aurora beam': 'ice',
            # Fighting moves
            'close combat': 'fighting', 'mach punch': 'fighting', 'brick break': 'fighting', 'focus blast': 'fighting',
            # Poison moves
            'sludge bomb': 'poison', 'poison jab': 'poison', 'toxic': 'poison', 'venoshock': 'poison',
            # Ground moves
            'earthquake': 'ground', 'dig': 'ground', 'mud slap': 'ground', 'bulldoze': 'ground',
            # Flying moves
            'air slash': 'flying', 'brave bird': 'flying', 'drill peck': 'flying', 'gust': 'flying',
            # Psychic moves
            'psychic': 'psychic', 'psyshock': 'psychic', 'confusion': 'psychic', 'zen headbutt': 'psychic',
            # Bug moves
            'bug buzz': 'bug', 'x-scissor': 'bug', 'signal beam': 'bug', 'pin missile': 'bug',
            # Rock moves
            'stone edge': 'rock', 'rock slide': 'rock', 'rock throw': 'rock', 'power gem': 'rock',
            # Ghost moves
            'shadow ball': 'ghost', 'shadow claw': 'ghost', 'hex': 'ghost', 'ominous wind': 'ghost',
            # Dragon moves
            'dragon claw': 'dragon', 'dragon pulse': 'dragon', 'dragon breath': 'dragon', 'outrage': 'dragon',
            # Dark moves
            'dark pulse': 'dark', 'crunch': 'dark', 'bite': 'dark', 'foul play': 'dark',
            # Steel moves
            'iron head': 'steel', 'flash cannon': 'steel', 'metal claw': 'steel', 'gyro ball': 'steel',
            # Fairy moves
            'moonblast': 'fairy', 'dazzling gleam': 'fairy', 'play rough': 'fairy', 'fairy wind': 'fairy',
            # Shadow moves (GameCube era)
            'shadow rush': 'shadow', 'shadow blast': 'shadow', 'shadow blitz': 'shadow', 'shadow break': 'shadow',
            # Normal moves
            'tackle': 'normal', 'quick attack': 'normal', 'body slam': 'normal', 'hyper beam': 'normal',
            # Status moves (no type)
            'protect': 'normal', 'substitute': 'normal', 'swords dance': 'normal', 'toxic': 'poison'
        }
        
        # Convert to lowercase for matching
        move_name_lower = move_name.lower()
        
        # Try exact match first
        if move_name_lower in move_type_mapping:
            return move_type_mapping[move_name_lower]
        
        # Try partial matches
        for move_pattern, move_type in move_type_mapping.items():
            if move_pattern in move_name_lower or move_name_lower in move_pattern:
                return move_type
        
        # Default to normal if no match found
        return 'normal'
    
    def _get_move_category_from_name(self, move_name: str) -> str:
        """Get move category from move name (simplified implementation)."""
        # Simplified move category mapping
        physical_moves = [
            'tackle', 'quick attack', 'body slam', 'hyper beam', 'earthquake', 'dig', 'mud slap',
            'bulldoze', 'stone edge', 'rock slide', 'rock throw', 'power gem', 'close combat',
            'mach punch', 'brick break', 'focus blast', 'air slash', 'brave bird', 'drill peck',
            'gust', 'bug buzz', 'x-scissor', 'signal beam', 'pin missile', 'shadow claw',
            'hex', 'ominous wind', 'dragon claw', 'dragon breath', 'outrage', 'crunch',
            'bite', 'foul play', 'iron head', 'metal claw', 'gyro ball', 'play rough',
            'shadow rush', 'shadow blitz', 'shadow break', 'fire punch', 'ice punch',
            'venoshock', 'poison jab', 'sludge bomb', 'thunder', 'thunderbolt', 'spark',
            'volt tackle', 'vine whip', 'razor leaf', 'seed bomb', 'blizzard', 'aurora beam',
            'flamethrower', 'ember', 'hydro pump', 'water gun', 'aqua jet'
        ]
        
        special_moves = [
            'fire blast', 'flamethrower', 'ember', 'surf', 'hydro pump', 'water gun',
            'aqua jet', 'solar beam', 'razor leaf', 'seed bomb', 'thunderbolt', 'thunder',
            'spark', 'volt tackle', 'ice beam', 'blizzard', 'ice punch', 'aurora beam',
            'focus blast', 'sludge bomb', 'poison jab', 'toxic', 'venoshock', 'bulldoze',
            'mud slap', 'air slash', 'brave bird', 'drill peck', 'gust', 'psychic',
            'psyshock', 'confusion', 'zen headbutt', 'bug buzz', 'x-scissor', 'signal beam',
            'pin missile', 'stone edge', 'rock slide', 'rock throw', 'power gem',
            'shadow ball', 'hex', 'ominous wind', 'dragon pulse', 'dragon breath',
            'outrage', 'dark pulse', 'bite', 'foul play', 'flash cannon', 'gyro ball',
            'moonblast', 'dazzling gleam', 'fairy wind', 'shadow blast', 'shadow wave'
        ]
        
        status_moves = [
            'protect', 'substitute', 'swords dance', 'toxic', 'thunder wave', 'will-o-wisp',
            'confuse ray', 'hypnosis', 'sleep powder', 'stun spore', 'poison powder',
            'leer', 'growl', 'tail whip', 'scary face', 'charm', 'attract', 'safeguard',
            'reflect', 'light screen', 'barrier', 'amnesia', 'harden', 'withdraw',
            'defense curl', 'minimize', 'double team', 'smokescreen', 'sand attack',
            'string shot', 'supersonic', 'thunder wave', 'glare', 'poison powder',
            'sleep powder', 'stun spore', 'spore', 'powder', 'rage powder'
        ]
        
        move_name_lower = move_name.lower()
        
        if move_name_lower in physical_moves:
            return 'physical'
        elif move_name_lower in special_moves:
            return 'special'
        elif move_name_lower in status_moves:
            return 'status'
        else:
            # Default to physical for unknown moves
            return 'physical'
