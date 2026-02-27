"""
GameCube era trading implementation.
Handles trading for Pokemon Colosseum, XD: Gale of Darkness, and Pokemon Box.
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .trading_methods import (
    BaseTradingInterface, TradingMethod, TradingProtocol,
    TradingSession, TradingOffer
)
from ..teambuilder.team import TeamEra
from ..core.pokemon import Pokemon, ShadowPokemon


class GameCubeTrading(BaseTradingInterface):
    """Trading interface for GameCube era Pokemon games."""
    
    def __init__(self, era: TeamEra):
        super().__init__(era)
        self.link_cable_connected = False
        self.wireless_adapter_connected = False
        self.pokemon_box_connected = False
        
    def _get_supported_methods(self) -> List[TradingMethod]:
        """Get supported trading methods for GameCube era."""
        methods = []
        
        if self.era in [TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
            methods.extend([
                TradingMethod.GAMECUBE_LINK_CABLE,
                TradingMethod.GAMECUBE_WIRELESS
            ])
        
        if self.era == TeamEra.POKEMON_BOX:
            methods.extend([
                TradingMethod.GAMECUBE_LINK_CABLE,
                TradingMethod.GAMECUBE_WIRELESS
            ])
        
        return methods
    
    def initialize_connection(self, method: TradingMethod) -> bool:
        """Initialize connection for GameCube trading."""
        if not self.is_method_supported(method):
            return False
        
        if method == TradingMethod.GAMECUBE_LINK_CABLE:
            # Simulate link cable connection
            self.link_cable_connected = True
            logger.info("GameCube Link Cable connected")
            return True
        
        elif method == TradingMethod.GAMECUBE_WIRELESS:
            # Simulate wireless adapter connection
            self.wireless_adapter_connected = True
            logger.info("GameCube Wireless Adapter connected")
            return True
        
        return False
    
    def create_trading_session(self, method: TradingMethod) -> Optional[TradingSession]:
        """Create a new GameCube trading session."""
        if not self.is_method_supported(method):
            return None
        
        session_id = str(uuid.uuid4())
        protocol = TradingProtocol.LINK_CABLE if method == TradingMethod.GAMECUBE_LINK_CABLE else TradingProtocol.WIRELESS_ADAPTER
        
        session = TradingSession(
            method=method,
            protocol=protocol,
            era=self.era,
            session_id=session_id,
            is_active=True,
            max_participants=2
        )
        
        self.active_sessions[session_id] = session
        logger.info(f"GameCube trading session created: {session_id}")
        return session
    
    def join_trading_session(self, session_id: str) -> bool:
        """Join an existing GameCube trading session."""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        if len(session.participants) >= session.max_participants:
            return False
        
        session.participants.append(f"Player_{len(session.participants) + 1}")
        logger.info(f"Joined GameCube trading session: {session_id}")
        return True
    
    def send_pokemon(self, session_id: str, pokemon: Pokemon) -> bool:
        """Send a Pokemon in a GameCube trading session."""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        if not session.is_active:
            return False
        
        # Validate Pokemon for GameCube trading
        issues = self.validate_pokemon_for_trading(pokemon)
        if issues:
            logger.warning(f"Cannot trade {pokemon.name}: {', '.join(issues)}")
            return False
        
        # GameCube-specific validation
        if self.era in [TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
            # Check for Shadow Pokemon compatibility
            if isinstance(pokemon, ShadowPokemon):
                if pokemon.shadow_level > 0:
                    print(f"Shadow Pokemon {pokemon.name} cannot be traded while shadowed")
                    return False
        
        logger.info(f"Sent {pokemon.name} via GameCube trading")
        return True
    
    def receive_pokemon(self, session_id: str) -> Optional[Pokemon]:
        """Receive a Pokemon in a GameCube trading session."""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        if not session.is_active:
            return None
        
        # Simulate receiving a Pokemon
        # In a real implementation, this would receive actual Pokemon data
        logger.info("Received Pokemon via GameCube trading")
        return None
    
    def close_session(self, session_id: str) -> bool:
        """Close a GameCube trading session."""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        session.is_active = False
        logger.info(f"Closed GameCube trading session: {session_id}")
        return True
    
    def transfer_to_pokemon_box(self, pokemon: Pokemon) -> bool:
        """Transfer Pokemon to Pokemon Box (if applicable)."""
        if self.era != TeamEra.POKEMON_BOX:
            return False
        
        # Validate Pokemon for Pokemon Box
        issues = self.validate_pokemon_for_trading(pokemon)
        if issues:
            logger.warning(f"Cannot transfer {pokemon.name} to Pokemon Box: {', '.join(issues)}")
            return False
        
        logger.info(f"Transferred {pokemon.name} to Pokemon Box")
        return True
    
    def transfer_from_pokemon_box(self, pokemon_id: int) -> Optional[Pokemon]:
        """Transfer Pokemon from Pokemon Box."""
        if self.era != TeamEra.POKEMON_BOX:
            return None
        
        # Simulate retrieving Pokemon from Box
        logger.info(f"Retrieved Pokemon {pokemon_id} from Pokemon Box")
        return None
    
    def purify_shadow_pokemon(self, shadow_pokemon: ShadowPokemon) -> bool:
        """Purify a Shadow Pokemon (Colosseum/XD specific)."""
        if self.era not in [TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
            return False
        
        if not isinstance(shadow_pokemon, ShadowPokemon):
            return False
        
        if shadow_pokemon.shadow_level <= 0:
            logger.warning(f"{shadow_pokemon.name} is not a Shadow Pokemon")
            return False
        
        # Simulate purification process
        shadow_pokemon.shadow_level = 0
        logger.info(f"Purified Shadow Pokemon {shadow_pokemon.name}")
        return True
    
    def get_shadow_pokemon_list(self) -> List[ShadowPokemon]:
        """Get list of available Shadow Pokemon (Colosseum/XD specific)."""
        if self.era not in [TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
            return []
        
        # Return list of Shadow Pokemon available in the game
        # This would be populated with actual Shadow Pokemon data
        return []
    
    def validate_pokemon_for_trading(self, pokemon: Pokemon) -> List[str]:
        """Validate if a Pokemon can be traded in GameCube era."""
        issues = super().validate_pokemon_for_trading(pokemon)
        
        # GameCube-specific validation
        if self.era in [TeamEra.COLOSSEUM, TeamEra.XD_GALE]:
            # Only Pokemon up to Gen 3 are available
            if pokemon.species_id > 386:
                issues.append(f"{pokemon.name} is not available in {self.era.value}")
            
            # Check for Shadow Pokemon restrictions
            if isinstance(pokemon, ShadowPokemon) and pokemon.shadow_level > 0:
                issues.append(f"Shadow Pokemon {pokemon.name} cannot be traded while shadowed")
        
        elif self.era == TeamEra.POKEMON_BOX:
            # Pokemon Box can store any Pokemon from Gen 3
            if pokemon.species_id > 386:
                issues.append(f"{pokemon.name} is not available in Pokemon Box")
        
        return issues

