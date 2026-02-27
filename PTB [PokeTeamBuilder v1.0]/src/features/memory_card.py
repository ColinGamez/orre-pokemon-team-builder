"""
GameCube Memory Card Support for Pokemon Team Builder.

Implements reading and writing of GameCube Memory Card (.gci) files,
specifically for Pokemon Colosseum and Pokemon XD: Gale of Darkness.

GCI (single-file export) format:
  - GCI header: 0x40 bytes (64 bytes)
  - Save data: variable length (multiple of 0x2000 / 8 KB blocks)

Supported games:
  - Pokemon Colosseum (GC6E/GC6J/GC6P)
  - Pokemon XD: Gale of Darkness (GXXE/GXXJ/GXXP)
  - Pokemon Box: Ruby & Sapphire (GPXE/GPXJ)

PTB native format: .ptbmc (JSON, human-readable)
"""

import struct
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
GCI_HEADER_SIZE = 0x40
GC_BLOCK_SIZE   = 0x2000

KNOWN_GAME_IDS = {
    b'GC6E': 'Pokemon Colosseum (US)',
    b'GC6J': 'Pokemon Colosseum (JP)',
    b'GC6P': 'Pokemon Colosseum (EU)',
    b'GXXE': 'Pokemon XD: Gale of Darkness (US)',
    b'GXXJ': 'Pokemon XD: Gale of Darkness (JP)',
    b'GXXP': 'Pokemon XD: Gale of Darkness (EU)',
    b'GPXE': 'Pokemon Box: Ruby & Sapphire (US)',
    b'GPXJ': 'Pokemon Box: Ruby & Sapphire (JP)',
}

COLOSSEUM_PARTY_SIZE = 6
XD_PARTY_SIZE        = 6
PTB_SAVE_VERSION     = 1

NATURES = [
    "Hardy","Lonely","Brave","Adamant","Naughty",
    "Bold","Docile","Relaxed","Impish","Lax",
    "Timid","Hasty","Serious","Jolly","Naive",
    "Modest","Mild","Quiet","Bashful","Rash",
    "Calm","Gentle","Sassy","Careful","Quirky",
]

# ── Enums ──────────────────────────────────────────────────────────────────────
class MemoryCardGame(Enum):
    COLOSSEUM   = "colosseum"
    XD_GALE     = "xd_gale"
    POKEMON_BOX = "pokemon_box"
    UNKNOWN     = "unknown"

class SlotStatus(Enum):
    EMPTY    = "empty"
    OCCUPIED = "occupied"
    CORRUPT  = "corrupt"

# ── Data Classes ───────────────────────────────────────────────────────────────
@dataclass
class GCIHeader:
    """Parsed 64-byte GCI file header."""
    game_id:       bytes
    maker_code:    bytes
    filename:      str
    modified_time: int
    block_count:   int
    file_size:     int
    raw_header:    bytes = field(repr=False)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'GCIHeader':
        if len(data) < GCI_HEADER_SIZE:
            raise ValueError(f"GCI header too short: {len(data)} bytes")
        game_id       = data[0x00:0x04]
        maker_code    = data[0x04:0x06]
        filename      = data[0x08:0x28].rstrip(b'\x00').decode('ascii', errors='replace')
        modified_time = struct.unpack_from('>I', data, 0x28)[0]
        block_count   = struct.unpack_from('>H', data, 0x38)[0]
        file_size     = struct.unpack_from('>I', data, 0x3C)[0]
        return cls(game_id=game_id, maker_code=maker_code, filename=filename,
                   modified_time=modified_time, block_count=block_count,
                   file_size=file_size, raw_header=data[:GCI_HEADER_SIZE])

    @property
    def game_name(self) -> str:
        return KNOWN_GAME_IDS.get(self.game_id, f"Unknown ({self.game_id!r})")

    @property
    def detected_game(self) -> MemoryCardGame:
        if self.game_id in (b'GC6E', b'GC6J', b'GC6P'):
            return MemoryCardGame.COLOSSEUM
        if self.game_id in (b'GXXE', b'GXXJ', b'GXXP'):
            return MemoryCardGame.XD_GALE
        if self.game_id in (b'GPXE', b'GPXJ'):
            return MemoryCardGame.POKEMON_BOX
        return MemoryCardGame.UNKNOWN

    @property
    def modified_datetime(self) -> datetime:
        try:
            return datetime.fromtimestamp(datetime(2000,1,1).timestamp() + self.modified_time)
        except (OSError, OverflowError):
            return datetime(2000, 1, 1)


@dataclass
class SavedPokemon:
    """A Pokemon stored in a Memory Card save slot."""
    slot_index:            int
    species_id:            int
    species_name:          str
    nickname:              str
    level:                 int
    nature:                str
    ability:               str
    held_item:             str
    is_shadow:             bool
    shadow_level:          int
    purification_progress: float
    moves:                 List[str]
    hp_iv:  int = 0; atk_iv: int = 0; def_iv: int = 0
    spa_iv: int = 0; spd_iv: int = 0; spe_iv: int = 0
    hp_ev:  int = 0; atk_ev: int = 0; def_ev: int = 0
    spa_ev: int = 0; spd_ev: int = 0; spe_ev: int = 0
    is_shiny: bool = False
    gender:   str  = "unknown"
    ot_name:  str  = ""
    ot_id:    int  = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SavedPokemon':
        return cls(**d)


@dataclass
class MemoryCardSlot:
    """A single save slot on a Memory Card."""
    slot_index:    int
    status:        SlotStatus
    game:          MemoryCardGame
    trainer_name:  str
    trainer_id:    int
    play_time_h:   int
    play_time_m:   int
    party:         List[SavedPokemon]         = field(default_factory=list)
    boxes:         Dict[str, List[SavedPokemon]] = field(default_factory=dict)
    purif_chamber: List[SavedPokemon]         = field(default_factory=list)
    checksum_ok:   bool                       = True
    raw_data:      bytes                      = field(default=b'', repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'slot_index':    self.slot_index,
            'status':        self.status.value,
            'game':          self.game.value,
            'trainer_name':  self.trainer_name,
            'trainer_id':    self.trainer_id,
            'play_time_h':   self.play_time_h,
            'play_time_m':   self.play_time_m,
            'party':         [p.to_dict() for p in self.party],
            'boxes':         {k: [p.to_dict() for p in v] for k, v in self.boxes.items()},
            'purif_chamber': [p.to_dict() for p in self.purif_chamber],
            'checksum_ok':   self.checksum_ok,
        }

    @property
    def total_pokemon(self) -> int:
        return len(self.party) + sum(len(v) for v in self.boxes.values()) + len(self.purif_chamber)

    @property
    def shadow_pokemon(self) -> List[SavedPokemon]:
        all_p = list(self.party)
        for box in self.boxes.values():
            all_p.extend(box)
        all_p.extend(self.purif_chamber)
        return [p for p in all_p if p.is_shadow]


@dataclass
class MemoryCard:
    """Represents a GameCube Memory Card (virtual or loaded from .gci/.ptbmc)."""
    card_size_mb: int  = 59
    slots:        List[MemoryCardSlot] = field(default_factory=list)
    source_file:  str  = ""
    card_label:   str  = "Memory Card A"
    created_at:   str  = field(default_factory=lambda: datetime.now().isoformat())
    modified_at:  str  = field(default_factory=lambda: datetime.now().isoformat())

    def get_occupied_slots(self) -> List[MemoryCardSlot]:
        return [s for s in self.slots if s.status == SlotStatus.OCCUPIED]

    def get_slot(self, index: int) -> Optional[MemoryCardSlot]:
        return next((s for s in self.slots if s.slot_index == index), None)

    def add_slot(self, slot: MemoryCardSlot) -> bool:
        for i, existing in enumerate(self.slots):
            if existing.slot_index == slot.slot_index:
                self.slots[i] = slot
                self.modified_at = datetime.now().isoformat()
                return True
        self.slots.append(slot)
        self.modified_at = datetime.now().isoformat()
        return True

    def remove_slot(self, index: int) -> bool:
        for i, slot in enumerate(self.slots):
            if slot.slot_index == index:
                self.slots.pop(i)
                self.modified_at = datetime.now().isoformat()
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'card_size_mb': self.card_size_mb,
            'card_label':   self.card_label,
            'source_file':  self.source_file,
            'created_at':   self.created_at,
            'modified_at':  self.modified_at,
            'slots':        [s.to_dict() for s in self.slots],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'MemoryCard':
        card = cls(
            card_size_mb=d.get('card_size_mb', 59),
            card_label=d.get('card_label', 'Memory Card A'),
            source_file=d.get('source_file', ''),
            created_at=d.get('created_at', datetime.now().isoformat()),
            modified_at=d.get('modified_at', datetime.now().isoformat()),
        )
        for sd in d.get('slots', []):
            slot = MemoryCardSlot(
                slot_index=sd.get('slot_index', 0),
                status=SlotStatus(sd.get('status', 'empty')),
                game=MemoryCardGame(sd.get('game', 'unknown')),
                trainer_name=sd.get('trainer_name', ''),
                trainer_id=sd.get('trainer_id', 0),
                play_time_h=sd.get('play_time_h', 0),
                play_time_m=sd.get('play_time_m', 0),
                party=[SavedPokemon.from_dict(p) for p in sd.get('party', [])],
                boxes={k: [SavedPokemon.from_dict(p) for p in v]
                       for k, v in sd.get('boxes', {}).items()},
                purif_chamber=[SavedPokemon.from_dict(p) for p in sd.get('purif_chamber', [])],
                checksum_ok=sd.get('checksum_ok', True),
            )
            card.slots.append(slot)
        return card


# ── GCI Parser ─────────────────────────────────────────────────────────────────
class GCIParser:
    """
    Parser for GameCube .gci save files.
    Performs best-effort extraction of trainer and Pokemon data.
    """

    # Approximate offsets in Colosseum/XD save data (after GCI header)
    COLO_TRAINER_NAME = 0x78
    COLO_TRAINER_ID   = 0x88
    COLO_PLAY_TIME    = 0x8C
    COLO_PARTY        = 0x498
    COLO_POKE_SIZE    = 0x138

    XD_TRAINER_NAME   = 0x78
    XD_TRAINER_ID     = 0x88
    XD_PLAY_TIME      = 0x8C
    XD_PARTY          = 0x4A8
    XD_POKE_SIZE      = 0x196

    # Gen 1-3 species names (Colosseum/XD only use up to #386)
    SPECIES = {
        1:"Bulbasaur",2:"Ivysaur",3:"Venusaur",4:"Charmander",5:"Charmeleon",
        6:"Charizard",7:"Squirtle",8:"Wartortle",9:"Blastoise",10:"Caterpie",
        11:"Metapod",12:"Butterfree",13:"Weedle",14:"Kakuna",15:"Beedrill",
        16:"Pidgey",17:"Pidgeotto",18:"Pidgeot",19:"Rattata",20:"Raticate",
        21:"Spearow",22:"Fearow",23:"Ekans",24:"Arbok",25:"Pikachu",26:"Raichu",
        27:"Sandshrew",28:"Sandslash",29:"Nidoran-F",30:"Nidorina",31:"Nidoqueen",
        32:"Nidoran-M",33:"Nidorino",34:"Nidoking",35:"Clefairy",36:"Clefable",
        37:"Vulpix",38:"Ninetales",39:"Jigglypuff",40:"Wigglytuff",41:"Zubat",
        42:"Golbat",43:"Oddish",44:"Gloom",45:"Vileplume",46:"Paras",47:"Parasect",
        48:"Venonat",49:"Venomoth",50:"Diglett",51:"Dugtrio",52:"Meowth",53:"Persian",
        54:"Psyduck",55:"Golduck",56:"Mankey",57:"Primeape",58:"Growlithe",59:"Arcanine",
        60:"Poliwag",61:"Poliwhirl",62:"Poliwrath",63:"Abra",64:"Kadabra",65:"Alakazam",
        66:"Machop",67:"Machoke",68:"Machamp",69:"Bellsprout",70:"Weepinbell",
        71:"Victreebel",72:"Tentacool",73:"Tentacruel",74:"Geodude",75:"Graveler",
        76:"Golem",77:"Ponyta",78:"Rapidash",79:"Slowpoke",80:"Slowbro",
        81:"Magnemite",82:"Magneton",83:"Farfetchd",84:"Doduo",85:"Dodrio",
        86:"Seel",87:"Dewgong",88:"Grimer",89:"Muk",90:"Shellder",91:"Cloyster",
        92:"Gastly",93:"Haunter",94:"Gengar",95:"Onix",96:"Drowzee",97:"Hypno",
        98:"Krabby",99:"Kingler",100:"Voltorb",101:"Electrode",102:"Exeggcute",
        103:"Exeggutor",104:"Cubone",105:"Marowak",106:"Hitmonlee",107:"Hitmonchan",
        108:"Lickitung",109:"Koffing",110:"Weezing",111:"Rhyhorn",112:"Rhydon",
        113:"Chansey",114:"Tangela",115:"Kangaskhan",116:"Horsea",117:"Seadra",
        118:"Goldeen",119:"Seaking",120:"Staryu",121:"Starmie",122:"Mr. Mime",
        123:"Scyther",124:"Jynx",125:"Electabuzz",126:"Magmar",127:"Pinsir",
        128:"Tauros",129:"Magikarp",130:"Gyarados",131:"Lapras",132:"Ditto",
        133:"Eevee",134:"Vaporeon",135:"Jolteon",136:"Flareon",137:"Porygon",
        138:"Omanyte",139:"Omastar",140:"Kabuto",141:"Kabutops",142:"Aerodactyl",
        143:"Snorlax",144:"Articuno",145:"Zapdos",146:"Moltres",147:"Dratini",
        148:"Dragonair",149:"Dragonite",150:"Mewtwo",151:"Mew",
        152:"Chikorita",153:"Bayleef",154:"Meganium",155:"Cyndaquil",156:"Quilava",
        157:"Typhlosion",158:"Totodile",159:"Croconaw",160:"Feraligatr",
        161:"Sentret",162:"Furret",163:"Hoothoot",164:"Noctowl",165:"Ledyba",
        166:"Ledian",167:"Spinarak",168:"Ariados",169:"Crobat",170:"Chinchou",
        171:"Lanturn",172:"Pichu",173:"Cleffa",174:"Igglybuff",175:"Togepi",
        176:"Togetic",177:"Natu",178:"Xatu",179:"Mareep",180:"Flaaffy",
        181:"Ampharos",182:"Bellossom",183:"Marill",184:"Azumarill",185:"Sudowoodo",
        186:"Politoed",187:"Hoppip",188:"Skiploom",189:"Jumpluff",190:"Aipom",
        191:"Sunkern",192:"Sunflora",193:"Yanma",194:"Wooper",195:"Quagsire",
        196:"Espeon",197:"Umbreon",198:"Murkrow",199:"Slowking",200:"Misdreavus",
        201:"Unown",202:"Wobbuffet",203:"Girafarig",204:"Pineco",205:"Forretress",
        206:"Dunsparce",207:"Gligar",208:"Steelix",209:"Snubbull",210:"Granbull",
        211:"Qwilfish",212:"Scizor",213:"Shuckle",214:"Heracross",215:"Sneasel",
        216:"Teddiursa",217:"Ursaring",218:"Slugma",219:"Magcargo",220:"Swinub",
        221:"Piloswine",222:"Corsola",223:"Remoraid",224:"Octillery",225:"Delibird",
        226:"Mantine",227:"Skarmory",228:"Houndour",229:"Houndoom",230:"Kingdra",
        231:"Phanpy",232:"Donphan",233:"Porygon2",234:"Stantler",235:"Smeargle",
        236:"Tyrogue",237:"Hitmontop",238:"Smoochum",239:"Elekid",240:"Magby",
        241:"Miltank",242:"Blissey",243:"Raikou",244:"Entei",245:"Suicune",
        246:"Larvitar",247:"Pupitar",248:"Tyranitar",249:"Lugia",250:"Ho-Oh",
        251:"Celebi",252:"Treecko",253:"Grovyle",254:"Sceptile",255:"Torchic",
        256:"Combusken",257:"Blaziken",258:"Mudkip",259:"Marshtomp",260:"Swampert",
        261:"Poochyena",262:"Mightyena",263:"Zigzagoon",264:"Linoone",265:"Wurmple",
        266:"Silcoon",267:"Beautifly",268:"Cascoon",269:"Dustox",270:"Lotad",
        271:"Lombre",272:"Ludicolo",273:"Seedot",274:"Nuzleaf",275:"Shiftry",
        276:"Taillow",277:"Swellow",278:"Wingull",279:"Pelipper",280:"Ralts",
        281:"Kirlia",282:"Gardevoir",283:"Surskit",284:"Masquerain",285:"Shroomish",
        286:"Breloom",287:"Slakoth",288:"Vigoroth",289:"Slaking",290:"Nincada",
        291:"Ninjask",292:"Shedinja",293:"Whismur",294:"Loudred",295:"Exploud",
        296:"Makuhita",297:"Hariyama",298:"Azurill",299:"Nosepass",300:"Skitty",
        301:"Delcatty",302:"Sableye",303:"Mawile",304:"Aron",305:"Lairon",
        306:"Aggron",307:"Meditite",308:"Medicham",309:"Electrike",310:"Manectric",
        311:"Plusle",312:"Minun",313:"Volbeat",314:"Illumise",315:"Roselia",
        316:"Gulpin",317:"Swalot",318:"Carvanha",319:"Sharpedo",320:"Wailmer",
        321:"Wailord",322:"Numel",323:"Camerupt",324:"Torkoal",325:"Spoink",
        326:"Grumpig",327:"Spinda",328:"Trapinch",329:"Vibrava",330:"Flygon",
        331:"Cacnea",332:"Cacturne",333:"Swablu",334:"Altaria",335:"Zangoose",
        336:"Seviper",337:"Lunatone",338:"Solrock",339:"Barboach",340:"Whiscash",
        341:"Corphish",342:"Crawdaunt",343:"Baltoy",344:"Claydol",345:"Lileep",
        346:"Cradily",347:"Anorith",348:"Armaldo",349:"Feebas",350:"Milotic",
        351:"Castform",352:"Kecleon",353:"Shuppet",354:"Banette",355:"Duskull",
        356:"Dusclops",357:"Tropius",358:"Chimecho",359:"Absol",360:"Wynaut",
        361:"Snorunt",362:"Glalie",363:"Spheal",364:"Sealeo",365:"Walrein",
        366:"Clamperl",367:"Huntail",368:"Gorebyss",369:"Relicanth",370:"Luvdisc",
        371:"Bagon",372:"Shelgon",373:"Salamence",374:"Beldum",375:"Metang",
        376:"Metagross",377:"Regirock",378:"Regice",379:"Registeel",380:"Latias",
        381:"Latios",382:"Kyogre",383:"Groudon",384:"Rayquaza",385:"Jirachi",
        386:"Deoxys",
    }

    def species_name(self, sid: int) -> str:
        return self.SPECIES.get(sid, f"Pokemon #{sid}")

    def _gc_str(self, data: bytes, offset: int, max_len: int = 8) -> str:
        """Read a null-terminated GameCube 2-byte-per-char string."""
        chars = []
        for i in range(max_len):
            pos = offset + i * 2
            if pos + 1 >= len(data):
                break
            code = struct.unpack_from('>H', data, pos)[0]
            if code == 0:
                break
            if 0x41 <= code <= 0x5A or 0x61 <= code <= 0x7A or 0x30 <= code <= 0x39:
                chars.append(chr(code))
            else:
                chars.append('?')
        return ''.join(chars)

    def parse_gci_file(self, file_path: str) -> Tuple[Optional[GCIHeader], Optional[MemoryCardSlot]]:
        """Parse a .gci file. Returns (header, slot) or (None, None) on failure."""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"GCI not found: {file_path}")
            return None, None
        try:
            raw = path.read_bytes()
        except OSError as e:
            logger.error(f"Cannot read GCI: {e}")
            return None, None
        if len(raw) < GCI_HEADER_SIZE:
            logger.error("GCI too small")
            return None, None
        try:
            header = GCIHeader.from_bytes(raw[:GCI_HEADER_SIZE])
        except (ValueError, struct.error) as e:
            logger.error(f"Bad GCI header: {e}")
            return None, None
        slot = self._parse_save(header, raw[GCI_HEADER_SIZE:])
        return header, slot

    def _parse_save(self, header: GCIHeader, data: bytes) -> MemoryCardSlot:
        game = header.detected_game
        if game == MemoryCardGame.COLOSSEUM:
            return self._parse_colosseum(data)
        if game == MemoryCardGame.XD_GALE:
            return self._parse_xd(data)
        return MemoryCardSlot(slot_index=0, status=SlotStatus.OCCUPIED, game=game,
                              trainer_name="Unknown", trainer_id=0,
                              play_time_h=0, play_time_m=0, checksum_ok=False, raw_data=data)

    def _trainer_info(self, data: bytes, name_off: int, id_off: int, time_off: int):
        name = "Trainer"; tid = 0; ph = pm = 0
        try:
            if len(data) > name_off + 16:
                name = self._gc_str(data, name_off) or "Trainer"
            if len(data) > id_off + 4:
                tid = struct.unpack_from('>I', data, id_off)[0] & 0xFFFF
            if len(data) > time_off + 4:
                t = struct.unpack_from('>I', data, time_off)[0]
                ph = (t >> 16) & 0xFFFF; pm = (t >> 8) & 0xFF
        except struct.error:
            pass
        return name, tid, ph, pm

    def _parse_colosseum(self, data: bytes) -> MemoryCardSlot:
        name, tid, ph, pm = self._trainer_info(data, self.COLO_TRAINER_NAME,
                                                self.COLO_TRAINER_ID, self.COLO_PLAY_TIME)
        party = self._parse_party(data, self.COLO_PARTY, COLOSSEUM_PARTY_SIZE, self.COLO_POKE_SIZE)
        return MemoryCardSlot(slot_index=0, status=SlotStatus.OCCUPIED,
                              game=MemoryCardGame.COLOSSEUM, trainer_name=name,
                              trainer_id=tid, play_time_h=ph, play_time_m=pm,
                              party=party, raw_data=data)

    def _parse_xd(self, data: bytes) -> MemoryCardSlot:
        name, tid, ph, pm = self._trainer_info(data, self.XD_TRAINER_NAME,
                                               self.XD_TRAINER_ID, self.XD_PLAY_TIME)
        party = self._parse_party(data, self.XD_PARTY, XD_PARTY_SIZE, self.XD_POKE_SIZE)
        return MemoryCardSlot(slot_index=0, status=SlotStatus.OCCUPIED,
                              game=MemoryCardGame.XD_GALE, trainer_name=name,
                              trainer_id=tid, play_time_h=ph, play_time_m=pm,
                              party=party, raw_data=data)

    def _parse_party(self, data: bytes, offset: int, count: int, poke_size: int) -> List[SavedPokemon]:
        party = []
        for i in range(count):
            start = offset + i * poke_size
            if start + poke_size > len(data):
                break
            p = self._parse_pokemon(data[start:start + poke_size], i)
            if p and p.species_id > 0:
                party.append(p)
        return party

    def _parse_pokemon(self, data: bytes, idx: int) -> Optional[SavedPokemon]:
        if len(data) < 0x50:
            return None
        try:
            sid = struct.unpack_from('>H', data, 0x00)[0]
            if sid == 0 or sid > 386:
                return None
            level = max(1, min(100, data[0x04] if len(data) > 0x04 else 1))
            nature = NATURES[(data[0x08] if len(data) > 0x08 else 0) % 25]
            is_shadow = bool(data[0x10]) if len(data) > 0x10 else False
            shadow_level = max(0, min(5, data[0x11] if (is_shadow and len(data) > 0x11) else 0))
            nickname = self._gc_str(data, 0x18, 10) or self.species_name(sid)
            ivs = [0] * 6
            if len(data) >= 0x3C:
                iv_raw = struct.unpack_from('>I', data, 0x38)[0]
                for j in range(6):
                    ivs[j] = (iv_raw >> (25 - j * 5)) & 0x1F
            moves = []
            for m in range(4):
                off = 0x40 + m * 2
                if off + 2 <= len(data):
                    mid = struct.unpack_from('>H', data, off)[0]
                    if mid > 0:
                        moves.append(f"Move #{mid}")
            return SavedPokemon(
                slot_index=idx, species_id=sid, species_name=self.species_name(sid),
                nickname=nickname, level=level, nature=nature, ability="", held_item="",
                is_shadow=is_shadow, shadow_level=shadow_level, purification_progress=0.0,
                moves=moves, hp_iv=ivs[0], atk_iv=ivs[1], def_iv=ivs[2],
                spa_iv=ivs[3], spd_iv=ivs[4], spe_iv=ivs[5],
            )
        except (struct.error, IndexError) as e:
            logger.debug(f"Pokemon parse error at slot {idx}: {e}")
            return None


# ── Memory Card Manager ────────────────────────────────────────────────────────
class MemoryCardManager:
    """
    High-level manager for GameCube Memory Cards.

    Supports:
    - Loading .gci files (Colosseum, XD, Box)
    - Saving/loading PTB's .ptbmc format (JSON)
    - Creating new virtual memory cards
    - Exporting/importing teams to/from slots
    - Listing and deleting saved cards
    """

    PTBMC_EXT   = '.ptbmc'
    PTBMC_MAGIC = 'PTB_MEMORY_CARD_V1'

    def __init__(self, save_dir: Optional[str] = None):
        self.save_dir = Path(save_dir) if save_dir else Path.home() / '.ptb' / 'memory_cards'
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._parser = GCIParser()
        logger.info(f"MemoryCardManager ready, save_dir={self.save_dir}")

    # ── Load ───────────────────────────────────────────────────────────────────
    def load_gci(self, file_path: str) -> Optional[MemoryCard]:
        """Load a .gci file into a MemoryCard."""
        header, slot = self._parser.parse_gci_file(file_path)
        if header is None:
            return None
        card = MemoryCard(card_label=f"{header.game_name} Save", source_file=str(file_path))
        if slot:
            slot.slot_index = 0
            card.add_slot(slot)
        logger.info(f"Loaded GCI: {header.game_name}")
        return card

    def load_ptbmc(self, file_path: str) -> Optional[MemoryCard]:
        """Load a .ptbmc file."""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"PTBMC not found: {file_path}")
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Cannot load PTBMC: {e}")
            return None
        if data.get('magic') != self.PTBMC_MAGIC:
            logger.warning("PTBMC magic mismatch")
        try:
            card = MemoryCard.from_dict(data.get('card', {}))
            card.source_file = str(file_path)
            return card
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"PTBMC parse error: {e}")
            return None

    # ── Save ───────────────────────────────────────────────────────────────────
    def save_ptbmc(self, card: MemoryCard, file_path: Optional[str] = None) -> str:
        """Save a MemoryCard to a .ptbmc file. Returns the file path."""
        if file_path is None:
            safe = card.card_label.replace(' ', '_').replace('/', '_')
            file_path = str(self.save_dir / f"{safe}{self.PTBMC_EXT}")
        card.modified_at = datetime.now().isoformat()
        payload = {'magic': self.PTBMC_MAGIC, 'version': PTB_SAVE_VERSION, 'card': card.to_dict()}
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved PTBMC: {file_path}")
        return file_path

    # ── Card Management ────────────────────────────────────────────────────────
    def create_new_card(self, label: str = "Memory Card A", size_mb: int = 59) -> MemoryCard:
        """Create a new empty virtual Memory Card."""
        return MemoryCard(card_size_mb=size_mb, card_label=label)

    def list_saved_cards(self) -> List[Dict[str, Any]]:
        """List all .ptbmc files in the save directory."""
        cards = []
        for path in self.save_dir.glob(f'*{self.PTBMC_EXT}'):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                cd = data.get('card', {})
                cards.append({
                    'file':     str(path),
                    'label':    cd.get('card_label', path.stem),
                    'slots':    len(cd.get('slots', [])),
                    'modified': cd.get('modified_at', ''),
                    'size_mb':  cd.get('card_size_mb', 59),
                })
            except (OSError, json.JSONDecodeError):
                cards.append({'file': str(path), 'label': path.stem, 'slots': 0, 'error': True})
        return sorted(cards, key=lambda x: x.get('modified', ''), reverse=True)

    def delete_card(self, file_path: str) -> bool:
        """Delete a .ptbmc file."""
        path = Path(file_path)
        if path.exists() and path.suffix == self.PTBMC_EXT:
            path.unlink()
            return True
        return False

    # ── Team Integration ───────────────────────────────────────────────────────
    def export_team_to_slot(
        self, card: MemoryCard, slot_index: int, trainer_name: str,
        trainer_id: int, party: List[SavedPokemon],
        game: MemoryCardGame = MemoryCardGame.COLOSSEUM,
    ) -> MemoryCardSlot:
        """Write a team to a Memory Card slot."""
        slot = MemoryCardSlot(
            slot_index=slot_index, status=SlotStatus.OCCUPIED, game=game,
            trainer_name=trainer_name[:8], trainer_id=trainer_id & 0xFFFF,
            play_time_h=0, play_time_m=0, party=party[:6],
        )
        card.add_slot(slot)
        return slot

    def import_team_from_slot(self, card: MemoryCard, slot_index: int) -> Optional[List[SavedPokemon]]:
        """Read a team from a Memory Card slot."""
        slot = card.get_slot(slot_index)
        if slot is None or slot.status != SlotStatus.OCCUPIED:
            return None
        return list(slot.party)

    def get_all_shadow_pokemon(self, card: MemoryCard) -> List[Tuple[int, SavedPokemon]]:
        """Get all Shadow Pokemon across all slots."""
        return [(s.slot_index, p) for s in card.get_occupied_slots() for p in s.shadow_pokemon]

    # ── Checksum ───────────────────────────────────────────────────────────────
    @staticmethod
    def compute_checksum(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def verify_gci_size(file_path: str) -> bool:
        """Basic GCI integrity check — verifies minimum file size."""
        path = Path(file_path)
        return path.exists() and path.stat().st_size >= GCI_HEADER_SIZE + GC_BLOCK_SIZE
