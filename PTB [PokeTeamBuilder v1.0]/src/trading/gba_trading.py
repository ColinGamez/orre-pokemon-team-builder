"""
GBA Link Cable Trading Interface for PTB.

Implements the GBA↔GameCube link cable trading system used by:
  - Pokemon Colosseum (GBA party/box access)
  - Pokemon XD: Gale of Darkness (GBA party/box access)
  - Pokemon Box: Ruby & Sapphire (GBA storage)

The GBA link cable allowed:
  1. Reading GBA party and PC boxes from Colosseum/XD
  2. Trading Pokemon between GBA and GCN games
  3. Migrating purified Shadow Pokemon back to GBA
  4. Pokemon Box storing GBA Pokemon on GameCube memory card

This module provides:
  - GBALinkSession: Simulates an active GBA link cable connection
  - GBALinkCableTrading: High-level trading interface
  - GBACompatibilityChecker: Validates Pokemon for cross-platform transfer
"""

import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .trading_methods import (
    BaseTradingInterface, TradingMethod, TradingProtocol,
    TradingSession, TradingOffer
)
from ..teambuilder.team import TeamEra
from ..core.pokemon import Pokemon, ShadowPokemon, PokemonNature, PokemonStats, PokemonEV, PokemonIV

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────────────────────

class GBALinkStatus(Enum):
    """Status of the GBA link cable connection."""
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    TRANSFERRING = "transferring"
    ERROR        = "error"


class GBATransferDirection(Enum):
    """Direction of Pokemon transfer."""
    GBA_TO_GCN = "gba_to_gcn"   # GBA → Colosseum/XD
    GCN_TO_GBA = "gcn_to_gba"   # Colosseum/XD → GBA


class GBATransferResult(Enum):
    """Result of a transfer attempt."""
    SUCCESS          = "success"
    FAILED_SHADOW    = "failed_shadow"      # Shadow Pokemon can't be transferred
    FAILED_EGG       = "failed_egg"         # Eggs can't be transferred
    FAILED_ILLEGAL   = "failed_illegal"     # Illegal/hacked Pokemon
    FAILED_SPECIES   = "failed_species"     # Species not available in target game
    FAILED_NO_SPACE  = "failed_no_space"    # No space in target party/box
    FAILED_DISCONNECT= "failed_disconnect"  # Link cable disconnected


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class GBALinkSession:
    """
    Represents an active GBA link cable session.

    In the original games, this was established by:
    1. Connecting GBA to GameCube via official link cable
    2. Starting the GBA game
    3. Selecting "Trade" or "Move Pokemon" in Colosseum/XD
    """
    session_id:    str
    gba_game:      str          # "ruby", "sapphire", "emerald", "firered", "leafgreen"
    gcn_game:      str          # "colosseum", "xd_gale", "pokemon_box"
    status:        GBALinkStatus = GBALinkStatus.DISCONNECTED
    connected_at:  Optional[str] = None
    trainer_name:  str = ""
    trainer_id:    int = 0
    gba_party:     List[Dict[str, Any]] = field(default_factory=list)
    transfer_log:  List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id':   self.session_id,
            'gba_game':     self.gba_game,
            'gcn_game':     self.gcn_game,
            'status':       self.status.value,
            'connected_at': self.connected_at,
            'trainer_name': self.trainer_name,
            'trainer_id':   self.trainer_id,
            'gba_party':    self.gba_party,
            'transfer_log': self.transfer_log,
        }


@dataclass
class GBATransferRecord:
    """Record of a single Pokemon transfer."""
    transfer_id:   str
    session_id:    str
    direction:     GBATransferDirection
    species_id:    int
    species_name:  str
    nickname:      str
    level:         int
    result:        GBATransferResult
    timestamp:     str
    notes:         str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'transfer_id':  self.transfer_id,
            'session_id':   self.session_id,
            'direction':    self.direction.value,
            'species_id':   self.species_id,
            'species_name': self.species_name,
            'nickname':     self.nickname,
            'level':        self.level,
            'result':       self.result.value,
            'timestamp':    self.timestamp,
            'notes':        self.notes,
        }


# ── Compatibility Checker ──────────────────────────────────────────────────────

class GBACompatibilityChecker:
    """
    Validates Pokemon for GBA↔GCN transfer compatibility.

    Rules based on the original games:
    - Shadow Pokemon cannot be transferred to GBA (must be purified first)
    - Eggs cannot be transferred
    - Pokemon must be Gen 1-3 (species ID 1-386)
    - Pokemon Box can store any Gen 3 Pokemon
    - Colosseum/XD can receive any Gen 1-3 Pokemon from GBA
    """

    # Pokemon that require specific GBA games to obtain
    # (version exclusives that can only come from one game)
    RUBY_ONLY    = {273, 274, 275, 288, 289, 290, 291, 292, 335, 337, 338}
    SAPPHIRE_ONLY= {270, 271, 272, 285, 286, 287, 300, 301, 302, 303, 318, 319}
    FIRERED_ONLY = {1, 2, 3, 4, 5, 6, 37, 38, 52, 53, 58, 59, 83, 123, 125, 126}
    LEAFGREEN_ONLY={7, 8, 9, 10, 11, 12, 69, 70, 71, 79, 80, 102, 103, 108, 114}

    # Pokemon that cannot be obtained in any single GBA game without trading
    TRADE_REQUIRED = {
        # Trade evolutions
        64: "Kadabra → Alakazam",
        67: "Machoke → Machamp",
        75: "Graveler → Golem",
        93: "Haunter → Gengar",
        # Version exclusives requiring both games
    }

    def check_gba_to_gcn(
        self,
        species_id: int,
        is_shadow: bool,
        is_egg: bool,
        level: int,
        total_evs: int,
    ) -> Tuple[bool, str]:
        """
        Check if a Pokemon can be transferred from GBA to GCN.

        Returns:
            (can_transfer, reason)
        """
        if is_egg:
            return False, "Eggs cannot be transferred via link cable"

        if is_shadow:
            return False, "Shadow Pokemon cannot be transferred to GBA"

        if species_id == 0 or species_id > 386:
            return False, f"Species #{species_id} is not available in Gen 3"

        if level < 1 or level > 100:
            return False, f"Invalid level: {level}"

        if total_evs > 510:
            return False, f"Total EVs ({total_evs}) exceed maximum (510)"

        return True, "Compatible"

    def check_gcn_to_gba(
        self,
        species_id: int,
        is_shadow: bool,
        is_egg: bool,
        level: int,
    ) -> Tuple[bool, str]:
        """
        Check if a Pokemon can be transferred from GCN to GBA.

        Returns:
            (can_transfer, reason)
        """
        if is_shadow:
            return False, "Shadow Pokemon must be purified before transferring to GBA"

        if is_egg:
            return False, "Eggs cannot be transferred via link cable"

        if species_id == 0 or species_id > 386:
            return False, f"Species #{species_id} cannot be transferred to Gen 3 GBA"

        return True, "Compatible"

    def get_required_game(self, species_id: int) -> Optional[str]:
        """Get which GBA game is required to obtain a species."""
        if species_id in self.RUBY_ONLY:
            return "ruby"
        if species_id in self.SAPPHIRE_ONLY:
            return "sapphire"
        if species_id in self.FIRERED_ONLY:
            return "firered"
        if species_id in self.LEAFGREEN_ONLY:
            return "leafgreen"
        return None  # Available in multiple games


# ── GBA Link Cable Trading ─────────────────────────────────────────────────────

class GBALinkCableTrading(BaseTradingInterface):
    """
    GBA link cable trading interface for Colosseum, XD, and Pokemon Box.

    Simulates the GBA↔GameCube link cable connection and Pokemon transfer.
    """

    def __init__(self, era: TeamEra):
        super().__init__(era)
        self._checker = GBACompatibilityChecker()
        self._active_link_sessions: Dict[str, GBALinkSession] = {}
        self._transfer_history: List[GBATransferRecord] = []
        self._link_status = GBALinkStatus.DISCONNECTED

    def _get_supported_methods(self) -> List[TradingMethod]:
        """GBA link cable is supported in Colosseum, XD, and Pokemon Box."""
        if self.era in [TeamEra.COLOSSEUM, TeamEra.XD_GALE, TeamEra.POKEMON_BOX]:
            return [TradingMethod.GAMECUBE_LINK_CABLE]
        return []

    def initialize_connection(self, method: TradingMethod) -> bool:
        """Initialize GBA link cable connection."""
        if method != TradingMethod.GAMECUBE_LINK_CABLE:
            return False
        if not self.is_method_supported(method):
            logger.warning(f"GBA link cable not supported for era: {self.era.value}")
            return False
        self._link_status = GBALinkStatus.CONNECTED
        logger.info(f"GBA link cable connected for {self.era.value}")
        return True

    def create_trading_session(self, method: TradingMethod) -> Optional[TradingSession]:
        """Create a standard trading session (compatibility with base class)."""
        if not self.is_method_supported(method):
            return None
        session_id = str(uuid.uuid4())
        session = TradingSession(
            method=method,
            protocol=TradingProtocol.LINK_CABLE,
            era=self.era,
            session_id=session_id,
            is_active=True,
            max_participants=2,
        )
        self.active_sessions[session_id] = session
        return session

    def join_trading_session(self, session_id: str) -> bool:
        if session_id not in self.active_sessions:
            return False
        session = self.active_sessions[session_id]
        if len(session.participants) >= session.max_participants:
            return False
        session.participants.append(f"GBA_Player_{len(session.participants) + 1}")
        return True

    def send_pokemon(self, session_id: str, pokemon: Pokemon) -> bool:
        if session_id not in self.active_sessions:
            return False
        issues = self.validate_pokemon_for_trading(pokemon)
        if issues:
            logger.warning(f"Cannot trade {pokemon.name}: {', '.join(issues)}")
            return False
        logger.info(f"Sent {pokemon.name} via GBA link cable")
        return True

    def receive_pokemon(self, session_id: str) -> Optional[Pokemon]:
        if session_id not in self.active_sessions:
            return None
        logger.info("Received Pokemon via GBA link cable")
        return None

    def close_session(self, session_id: str) -> bool:
        if session_id not in self.active_sessions:
            return False
        self.active_sessions[session_id].is_active = False
        return True

    # ── GBA-Specific Methods ───────────────────────────────────────────────────

    def create_gba_link_session(
        self,
        gba_game: str,
        trainer_name: str = "",
        trainer_id: int = 0,
    ) -> GBALinkSession:
        """
        Create a new GBA link cable session.

        Args:
            gba_game:     GBA game name ("ruby", "sapphire", etc.)
            trainer_name: GBA trainer name
            trainer_id:   GBA trainer ID

        Returns:
            New GBALinkSession
        """
        session_id = str(uuid.uuid4())
        gcn_game = {
            TeamEra.COLOSSEUM:   "colosseum",
            TeamEra.XD_GALE:     "xd_gale",
            TeamEra.POKEMON_BOX: "pokemon_box",
        }.get(self.era, "unknown")

        session = GBALinkSession(
            session_id=session_id,
            gba_game=gba_game,
            gcn_game=gcn_game,
            status=GBALinkStatus.CONNECTED,
            connected_at=datetime.now().isoformat(),
            trainer_name=trainer_name,
            trainer_id=trainer_id,
        )
        self._active_link_sessions[session_id] = session
        logger.info(f"GBA link session created: {session_id} ({gba_game} ↔ {gcn_game})")
        return session

    def load_gba_party_from_save(
        self,
        session_id: str,
        gba_save_data: Dict[str, Any],
    ) -> bool:
        """
        Load GBA party data into a link session from parsed save data.

        Args:
            session_id:    Link session ID
            gba_save_data: Parsed GBA save dict (from GBASaveParser)

        Returns:
            True on success
        """
        if session_id not in self._active_link_sessions:
            return False

        session = self._active_link_sessions[session_id]
        party_data = gba_save_data.get('party', {})
        session.gba_party = party_data.get('pokemon', [])
        session.trainer_name = gba_save_data.get('info', {}).get('trainer_name', '')
        session.trainer_id   = gba_save_data.get('info', {}).get('trainer_id', 0)
        logger.info(f"Loaded {len(session.gba_party)} Pokemon into session {session_id}")
        return True

    def transfer_gba_to_gcn(
        self,
        session_id: str,
        pokemon_data: Dict[str, Any],
    ) -> GBATransferRecord:
        """
        Transfer a Pokemon from GBA to GCN.

        Args:
            session_id:   Link session ID
            pokemon_data: PK3Pokemon dict from GBA save

        Returns:
            GBATransferRecord with the result
        """
        transfer_id = str(uuid.uuid4())
        species_id   = pokemon_data.get('species_id', 0)
        species_name = pokemon_data.get('species_name', f"Pokemon #{species_id}")
        nickname     = pokemon_data.get('nickname', species_name)
        level        = pokemon_data.get('level', 1)
        is_egg       = pokemon_data.get('is_egg', False)
        total_evs    = sum([
            pokemon_data.get('hp_ev', 0), pokemon_data.get('atk_ev', 0),
            pokemon_data.get('def_ev', 0), pokemon_data.get('spe_ev', 0),
            pokemon_data.get('spa_ev', 0), pokemon_data.get('spd_ev', 0),
        ])

        can_transfer, reason = self._checker.check_gba_to_gcn(
            species_id=species_id,
            is_shadow=False,
            is_egg=is_egg,
            level=level,
            total_evs=total_evs,
        )

        result = GBATransferResult.SUCCESS if can_transfer else GBATransferResult.FAILED_ILLEGAL

        record = GBATransferRecord(
            transfer_id=transfer_id,
            session_id=session_id,
            direction=GBATransferDirection.GBA_TO_GCN,
            species_id=species_id,
            species_name=species_name,
            nickname=nickname,
            level=level,
            result=result,
            timestamp=datetime.now().isoformat(),
            notes=reason if not can_transfer else "",
        )
        self._transfer_history.append(record)

        if session_id in self._active_link_sessions:
            self._active_link_sessions[session_id].transfer_log.append(record.to_dict())

        logger.info(f"GBA→GCN transfer: {species_name} Lv.{level} — {result.value}")
        return record

    def transfer_gcn_to_gba(
        self,
        session_id: str,
        pokemon: Pokemon,
    ) -> GBATransferRecord:
        """
        Transfer a Pokemon from GCN to GBA.

        Args:
            session_id: Link session ID
            pokemon:    Pokemon to transfer

        Returns:
            GBATransferRecord with the result
        """
        transfer_id = str(uuid.uuid4())
        is_shadow = isinstance(pokemon, ShadowPokemon) and pokemon.shadow_level > 0

        can_transfer, reason = self._checker.check_gcn_to_gba(
            species_id=pokemon.species_id,
            is_shadow=is_shadow,
            is_egg=False,
            level=pokemon.level,
        )

        if is_shadow:
            result = GBATransferResult.FAILED_SHADOW
        elif not can_transfer:
            result = GBATransferResult.FAILED_ILLEGAL
        else:
            result = GBATransferResult.SUCCESS

        record = GBATransferRecord(
            transfer_id=transfer_id,
            session_id=session_id,
            direction=GBATransferDirection.GCN_TO_GBA,
            species_id=pokemon.species_id,
            species_name=pokemon.name,
            nickname=pokemon.name,
            level=pokemon.level,
            result=result,
            timestamp=datetime.now().isoformat(),
            notes=reason if not can_transfer else "",
        )
        self._transfer_history.append(record)

        if session_id in self._active_link_sessions:
            self._active_link_sessions[session_id].transfer_log.append(record.to_dict())

        logger.info(f"GCN→GBA transfer: {pokemon.name} Lv.{pokemon.level} — {result.value}")
        return record

    def get_session(self, session_id: str) -> Optional[GBALinkSession]:
        """Get a link session by ID."""
        return self._active_link_sessions.get(session_id)

    def get_transfer_history(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get transfer history, optionally filtered by session."""
        records = self._transfer_history
        if session_id:
            records = [r for r in records if r.session_id == session_id]
        return [r.to_dict() for r in records]

    def disconnect(self, session_id: str) -> bool:
        """Disconnect a GBA link session."""
        if session_id in self._active_link_sessions:
            self._active_link_sessions[session_id].status = GBALinkStatus.DISCONNECTED
            logger.info(f"GBA link session disconnected: {session_id}")
            return True
        return False

    def validate_pokemon_for_trading(self, pokemon: Pokemon) -> List[str]:
        """Validate a Pokemon for GBA link cable trading."""
        issues = []

        if isinstance(pokemon, ShadowPokemon) and pokemon.shadow_level > 0:
            issues.append(f"{pokemon.name} is a Shadow Pokemon — must be purified first")

        if pokemon.species_id > 386:
            issues.append(f"{pokemon.name} (#{pokemon.species_id}) is not a Gen 1-3 Pokemon")

        if pokemon.level < 1 or pokemon.level > 100:
            issues.append(f"Invalid level: {pokemon.level}")

        return issues

    @property
    def link_status(self) -> GBALinkStatus:
        return self._link_status

    @property
    def active_link_sessions(self) -> Dict[str, GBALinkSession]:
        return dict(self._active_link_sessions)
