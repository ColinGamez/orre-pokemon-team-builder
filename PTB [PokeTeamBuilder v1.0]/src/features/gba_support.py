"""
GBA (Game Boy Advance) Pokemon Game Support for PTB.

Implements full Gen 3 GBA save file parsing and Pokemon data extraction
for the games that connected to Pokemon Colosseum and XD via link cable:

  - Pokemon Ruby (AXV)
  - Pokemon Sapphire (AXP)
  - Pokemon Emerald (BPE)
  - Pokemon FireRed (BPR)
  - Pokemon LeafGreen (BPG)

Gen 3 Save File Format:
  - Two 57344-byte (0xE000) save sections, alternating (A/B slots)
  - Each slot contains 14 sections of 4096 bytes (0x1000) each
  - Sections are identified by a section ID (0-13) in the footer
  - Section footer: 12 bytes at end of each section
    - 0xFF8: section ID (2 bytes)
    - 0xFFA: checksum (2 bytes)
    - 0xFFC: save index (4 bytes)
    - 0xFFE: section size (4 bytes) — always 0x1000 for GBA

Gen 3 Pokemon (PK3) Structure:
  - 100 bytes total
  - 32 bytes unencrypted header
  - 48 bytes encrypted data (4 substructures × 12 bytes)
  - 20 bytes status/misc data
  - Encryption key: personality_value XOR trainer_id XOR secret_id

GBA→GCN Link Cable Transfer:
  - GBA connects to GameCube via official link cable
  - Colosseum/XD reads GBA party and boxes
  - Traded Pokemon are converted to GCN format
  - Shadow Pokemon can be traded back to GBA after purification
"""

import struct
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

GBA_SAVE_SIZE       = 0x20000   # 128 KB total save file
GBA_SECTION_SIZE    = 0x1000    # 4 KB per section
GBA_SLOT_SIZE       = 0xE000    # 57344 bytes per save slot (14 sections)
GBA_SECTION_COUNT   = 14        # Sections per slot
GBA_FOOTER_OFFSET   = 0xFF8     # Section footer offset within section
GBA_SECTION_ID_OFF  = 0xFF8     # Section ID offset in footer
GBA_CHECKSUM_OFF    = 0xFFA     # Checksum offset in footer
GBA_SAVE_INDEX_OFF  = 0xFFC     # Save index offset in footer

PK3_SIZE            = 100       # Bytes per Pokemon in Gen 3
PK3_HEADER_SIZE     = 32        # Unencrypted header
PK3_DATA_SIZE       = 48        # Encrypted data (4 × 12 bytes)
PK3_STATUS_SIZE     = 20        # Status/misc data

# Section IDs
SECTION_TRAINER_INFO    = 0     # Trainer name, ID, play time, money
SECTION_TEAM_ITEMS      = 1     # Party Pokemon + items
SECTION_GAME_STATE      = 2     # Game flags, events
SECTION_MISC_DATA       = 3     # Misc game data
SECTION_RIVAL_INFO      = 4     # Rival name
SECTION_PC_BUFFER_A     = 5     # PC box data (part 1)
SECTION_PC_BUFFER_B     = 6     # PC box data (part 2)
SECTION_PC_BUFFER_C     = 7     # PC box data (part 3)
SECTION_PC_BUFFER_D     = 8     # PC box data (part 4)
SECTION_PC_BUFFER_E     = 9     # PC box data (part 5)
SECTION_PC_BUFFER_F     = 10    # PC box data (part 6)
SECTION_PC_BUFFER_G     = 11    # PC box data (part 7)
SECTION_PC_BUFFER_H     = 12    # PC box data (part 8)
SECTION_PC_BUFFER_I     = 13    # PC box data (part 9)

# Party offset within section 1
PARTY_COUNT_OFFSET  = 0x234     # Number of Pokemon in party
PARTY_DATA_OFFSET   = 0x238     # Start of party Pokemon data

# PC box layout
PC_BOX_COUNT        = 14        # Boxes per game
PC_BOX_SIZE         = 30        # Pokemon per box
PC_POKEMON_SIZE     = 80        # Bytes per PC Pokemon (no status data)

# Game codes (first 4 bytes of ROM header, read from save)
GAME_CODES = {
    b'AXV\x00': 'Pokemon Ruby (US)',
    b'AXP\x00': 'Pokemon Sapphire (US)',
    b'BPE\x00': 'Pokemon Emerald (US)',
    b'BPR\x00': 'Pokemon FireRed (US)',
    b'BPG\x00': 'Pokemon LeafGreen (US)',
    b'AXV\x01': 'Pokemon Ruby (EU)',
    b'AXP\x01': 'Pokemon Sapphire (EU)',
    b'BPE\x01': 'Pokemon Emerald (EU)',
    b'BPR\x01': 'Pokemon FireRed (EU)',
    b'BPG\x01': 'Pokemon LeafGreen (EU)',
    b'AXV\x02': 'Pokemon Ruby (JP)',
    b'AXP\x02': 'Pokemon Sapphire (JP)',
    b'BPE\x02': 'Pokemon Emerald (JP)',
    b'BPR\x02': 'Pokemon FireRed (JP)',
    b'BPG\x02': 'Pokemon LeafGreen (JP)',
}

# Nature names
NATURES = [
    "Hardy","Lonely","Brave","Adamant","Naughty",
    "Bold","Docile","Relaxed","Impish","Lax",
    "Timid","Hasty","Serious","Jolly","Naive",
    "Modest","Mild","Quiet","Bashful","Rash",
    "Calm","Gentle","Sassy","Careful","Quirky",
]

# Substructure order lookup (personality value % 24)
# Each letter represents a substructure: G=Growth, A=Attacks, E=EVs/Condition, M=Misc
SUBSTRUCTURE_ORDER = [
    "GAEM","GAME","GEAM","GEMA","GMAE","GMEA",
    "AGEM","AGME","AEGM","AEMG","AMGE","AMEG",
    "EGAM","EGMA","EAGM","EAMG","EMGA","EMAG",
    "MGAE","MGEA","MAGE","MAEG","MEGA","MEAG",
]

# Version-exclusive Pokemon (for compatibility checking)
RUBY_EXCLUSIVES    = {273,274,275,288,289,290,291,292,335,337,338,339,340,
                      341,342,343,344,345,346,347,348,369,370}
SAPPHIRE_EXCLUSIVES= {270,271,272,285,286,287,300,301,302,303,318,319,320,
                      321,333,334,336,349,350,363,364,365,366,367,368}
FIRERED_EXCLUSIVES = {1,2,3,4,5,6,37,38,52,53,58,59,83,123,125,126,
                      143,144,145,146,150,151}
LEAFGREEN_EXCLUSIVES={7,8,9,10,11,12,69,70,71,79,80,102,103,108,114,
                       115,116,117,118,119,120,121,147,148,149}

# Pokemon that can be traded from GBA to GCN (Colosseum/XD)
# All Gen 1-3 Pokemon are tradeable, but some require specific games
GBA_TO_GCN_COMPATIBLE = set(range(1, 387))  # All Gen 1-3

# Pokemon available in Colosseum (snaggable + tradeable in)
COLOSSEUM_AVAILABLE = {
    # Starters (via trade from GBA)
    1,4,7,152,155,158,252,255,258,
    # Snaggable Shadow Pokemon in Colosseum
    37,38,52,53,58,59,83,85,86,87,88,89,90,91,92,93,94,95,96,97,
    100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,
    116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,
    132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,
    148,149,150,151,
    # Gen 3 available via trade
    252,253,254,255,256,257,258,259,260,
}

# Pokemon available in XD: Gale of Darkness (snaggable + tradeable in)
XD_AVAILABLE = {
    # All Colosseum Pokemon plus XD-specific
    *COLOSSEUM_AVAILABLE,
    # XD Shadow Pokemon (additional)
    16,17,18,21,22,25,26,27,28,29,30,31,32,33,34,35,36,39,40,41,42,
    43,44,45,46,47,48,49,50,51,54,55,56,57,60,61,62,63,64,65,66,67,
    68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,84,
    # XD-exclusive: Lugia (Shadow)
    249,
    # Bonsly (pre-evolution, XD exclusive)
    438,
}


# ── Enums ──────────────────────────────────────────────────────────────────────

class GBAGame(Enum):
    """GBA Pokemon games."""
    RUBY        = "ruby"
    SAPPHIRE    = "sapphire"
    EMERALD     = "emerald"
    FIRERED     = "firered"
    LEAFGREEN   = "leafgreen"
    UNKNOWN     = "unknown"


class GBARegion(Enum):
    """GBA game regions."""
    US  = "us"
    EU  = "eu"
    JP  = "jp"
    UNKNOWN = "unknown"


class TransferCompatibility(Enum):
    """GBA→GCN transfer compatibility status."""
    COMPATIBLE      = "compatible"      # Can be transferred
    INCOMPATIBLE    = "incompatible"    # Cannot be transferred
    REQUIRES_PURIFY = "requires_purify" # Shadow Pokemon, needs purification first
    VERSION_LOCKED  = "version_locked"  # Requires specific GBA game


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class GBASaveInfo:
    """Metadata about a GBA save file."""
    file_path:    str
    game:         GBAGame
    region:       GBARegion
    game_name:    str
    trainer_name: str
    trainer_id:   int
    secret_id:    int
    play_time_h:  int
    play_time_m:  int
    play_time_s:  int
    money:        int
    badges:       int
    is_valid:     bool = True
    error:        str  = ""
    slot_used:    int  = 0   # Which save slot (A=0 or B=1) was loaded

    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_path':    self.file_path,
            'game':         self.game.value,
            'region':       self.region.value,
            'game_name':    self.game_name,
            'trainer_name': self.trainer_name,
            'trainer_id':   self.trainer_id,
            'secret_id':    self.secret_id,
            'play_time_h':  self.play_time_h,
            'play_time_m':  self.play_time_m,
            'play_time_s':  self.play_time_s,
            'money':        self.money,
            'badges':       self.badges,
            'is_valid':     self.is_valid,
            'error':        self.error,
            'slot_used':    self.slot_used,
        }


@dataclass
class PK3Pokemon:
    """
    A Pokemon in Gen 3 (GBA) format.
    Fully decrypted and parsed from the binary PK3 structure.
    """
    # Identity
    personality_value: int
    ot_id:             int
    ot_secret_id:      int
    nickname:          str
    language:          int
    ot_name:           str
    markings:          int
    checksum:          int

    # Growth substructure
    species_id:        int
    item_id:           int
    experience:        int
    pp_bonuses:        int
    friendship:        int
    unknown_growth:    int

    # Attacks substructure
    move1_id:          int
    move2_id:          int
    move3_id:          int
    move4_id:          int
    move1_pp:          int
    move2_pp:          int
    move3_pp:          int
    move4_pp:          int

    # EVs/Condition substructure
    hp_ev:             int
    atk_ev:            int
    def_ev:            int
    spe_ev:            int
    spa_ev:            int
    spd_ev:            int
    coolness:          int
    beauty:            int
    cuteness:          int
    smartness:         int
    toughness:         int
    feel:              int

    # Misc substructure
    pokerus:           int
    met_location:      int
    origins_info:      int
    iv_egg_ability:    int
    ribbons_obedience: int

    # Status (unencrypted)
    status_condition:  int
    level:             int
    pokerus_days:      int
    current_hp:        int
    total_hp:          int
    attack:            int
    defense:           int
    speed:             int
    sp_attack:         int
    sp_defense:        int

    # Derived fields (computed after parsing)
    species_name:      str = ""
    nature:            str = ""
    is_shiny:          bool = False
    is_egg:            bool = False
    gender:            str = "unknown"
    ability_slot:      int = 0
    hp_iv:             int = 0
    atk_iv:            int = 0
    def_iv:            int = 0
    spe_iv:            int = 0
    spa_iv:            int = 0
    spd_iv:            int = 0
    move_names:        List[str] = field(default_factory=list)
    item_name:         str = ""
    met_game:          str = ""
    met_level:         int = 0
    is_fateful:        bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'PK3Pokemon':
        return cls(**d)

    @property
    def transfer_compatibility(self) -> TransferCompatibility:
        """Check if this Pokemon can be transferred to GCN."""
        if self.is_egg:
            return TransferCompatibility.INCOMPATIBLE
        if self.species_id == 0 or self.species_id > 386:
            return TransferCompatibility.INCOMPATIBLE
        return TransferCompatibility.COMPATIBLE

    @property
    def display_name(self) -> str:
        """Nickname if different from species name, else species name."""
        if self.nickname and self.nickname != self.species_name:
            return f"{self.nickname} ({self.species_name})"
        return self.species_name or f"Pokemon #{self.species_id}"


@dataclass
class GBAParty:
    """The 6-Pokemon party from a GBA save."""
    pokemon: List[PK3Pokemon] = field(default_factory=list)
    count:   int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {'count': self.count, 'pokemon': [p.to_dict() for p in self.pokemon]}


@dataclass
class GBABox:
    """A single PC box from a GBA save."""
    box_index: int
    name:      str
    pokemon:   List[PK3Pokemon] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'box_index': self.box_index,
            'name':      self.name,
            'pokemon':   [p.to_dict() for p in self.pokemon],
        }


@dataclass
class GBASave:
    """Complete parsed GBA save file."""
    info:   GBASaveInfo
    party:  GBAParty
    boxes:  List[GBABox] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'info':  self.info.to_dict(),
            'party': self.party.to_dict(),
            'boxes': [b.to_dict() for b in self.boxes],
        }

    @property
    def all_pokemon(self) -> List[PK3Pokemon]:
        """All Pokemon across party and boxes."""
        result = list(self.party.pokemon)
        for box in self.boxes:
            result.extend(box.pokemon)
        return result

    @property
    def transferable_pokemon(self) -> List[PK3Pokemon]:
        """Pokemon that can be transferred to GCN."""
        return [p for p in self.all_pokemon
                if p.transfer_compatibility == TransferCompatibility.COMPATIBLE]


# ── Species / Move / Item Name Tables ─────────────────────────────────────────

# Gen 3 species names (indices 1-386)
GEN3_SPECIES = {
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
    81:"Magnemite",82:"Magneton",83:"Farfetch'd",84:"Doduo",85:"Dodrio",
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

# Gen 3 move names (partial — most common moves)
GEN3_MOVES = {
    0:"---",1:"Pound",2:"Karate Chop",3:"Double Slap",4:"Comet Punch",
    5:"Mega Punch",6:"Pay Day",7:"Fire Punch",8:"Ice Punch",9:"Thunder Punch",
    10:"Scratch",11:"Vice Grip",12:"Guillotine",13:"Razor Wind",14:"Swords Dance",
    15:"Cut",16:"Gust",17:"Wing Attack",18:"Whirlwind",19:"Fly",
    20:"Bind",21:"Slam",22:"Vine Whip",23:"Stomp",24:"Double Kick",
    25:"Mega Kick",26:"Jump Kick",27:"Rolling Kick",28:"Sand Attack",29:"Headbutt",
    30:"Horn Attack",31:"Fury Attack",32:"Horn Drill",33:"Tackle",34:"Body Slam",
    35:"Wrap",36:"Take Down",37:"Thrash",38:"Double-Edge",39:"Tail Whip",
    40:"Poison Sting",41:"Twineedle",42:"Pin Missile",43:"Leer",44:"Bite",
    45:"Growl",46:"Roar",47:"Sing",48:"Supersonic",49:"Sonic Boom",
    50:"Disable",51:"Acid",52:"Ember",53:"Flamethrower",54:"Mist",
    55:"Water Gun",56:"Hydro Pump",57:"Surf",58:"Ice Beam",59:"Blizzard",
    60:"Psybeam",61:"Bubble Beam",62:"Aurora Beam",63:"Hyper Beam",64:"Peck",
    65:"Drill Peck",66:"Submission",67:"Low Kick",68:"Counter",69:"Seismic Toss",
    70:"Strength",71:"Absorb",72:"Mega Drain",73:"Leech Seed",74:"Growth",
    75:"Razor Leaf",76:"Solar Beam",77:"Poison Powder",78:"Stun Spore",79:"Sleep Powder",
    80:"Petal Dance",81:"String Shot",82:"Dragon Rage",83:"Fire Spin",84:"Thunder Shock",
    85:"Thunderbolt",86:"Thunder Wave",87:"Thunder",88:"Rock Throw",89:"Earthquake",
    90:"Fissure",91:"Dig",92:"Toxic",93:"Confusion",94:"Psychic",
    95:"Hypnosis",96:"Meditate",97:"Agility",98:"Quick Attack",99:"Rage",
    100:"Teleport",101:"Night Shade",102:"Mimic",103:"Screech",104:"Double Team",
    105:"Recover",106:"Harden",107:"Minimize",108:"Smokescreen",109:"Confuse Ray",
    110:"Withdraw",111:"Defense Curl",112:"Barrier",113:"Light Screen",114:"Haze",
    115:"Reflect",116:"Focus Energy",117:"Bide",118:"Metronome",119:"Mirror Move",
    120:"Self-Destruct",121:"Egg Bomb",122:"Lick",123:"Smog",124:"Sludge",
    125:"Bone Club",126:"Fire Blast",127:"Waterfall",128:"Clamp",129:"Swift",
    130:"Skull Bash",131:"Spike Cannon",132:"Constrict",133:"Amnesia",134:"Kinesis",
    135:"Soft-Boiled",136:"Hi Jump Kick",137:"Glare",138:"Dream Eater",139:"Poison Gas",
    140:"Barrage",141:"Leech Life",142:"Lovely Kiss",143:"Sky Attack",144:"Transform",
    145:"Bubble",146:"Dizzy Punch",147:"Spore",148:"Flash",149:"Psywave",
    150:"Splash",151:"Acid Armor",152:"Crabhammer",153:"Explosion",154:"Fury Swipes",
    155:"Bonemerang",156:"Rest",157:"Rock Slide",158:"Hyper Fang",159:"Sharpen",
    160:"Conversion",161:"Tri Attack",162:"Super Fang",163:"Slash",164:"Substitute",
    165:"Struggle",166:"Sketch",167:"Triple Kick",168:"Thief",169:"Spider Web",
    170:"Mind Reader",171:"Nightmare",172:"Flame Wheel",173:"Snore",174:"Curse",
    175:"Flail",176:"Conversion 2",177:"Aeroblast",178:"Cotton Spore",179:"Reversal",
    180:"Spite",181:"Powder Snow",182:"Protect",183:"Mach Punch",184:"Scary Face",
    185:"Faint Attack",186:"Sweet Kiss",187:"Belly Drum",188:"Sludge Bomb",
    189:"Mud-Slap",190:"Octazooka",191:"Spikes",192:"Zap Cannon",193:"Foresight",
    194:"Destiny Bond",195:"Perish Song",196:"Icy Wind",197:"Detect",198:"Bone Rush",
    199:"Lock-On",200:"Outrage",201:"Sandstorm",202:"Giga Drain",203:"Endure",
    204:"Charm",205:"Rollout",206:"False Swipe",207:"Swagger",208:"Milk Drink",
    209:"Spark",210:"Fury Cutter",211:"Steel Wing",212:"Mean Look",213:"Attract",
    214:"Sleep Talk",215:"Heal Bell",216:"Return",217:"Present",218:"Frustration",
    219:"Safeguard",220:"Pain Split",221:"Sacred Fire",222:"Magnitude",223:"Dynamic Punch",
    224:"Megahorn",225:"Dragon Breath",226:"Baton Pass",227:"Encore",228:"Pursuit",
    229:"Rapid Spin",230:"Sweet Scent",231:"Iron Tail",232:"Metal Claw",233:"Vital Throw",
    234:"Morning Sun",235:"Synthesis",236:"Moonlight",237:"Hidden Power",238:"Cross Chop",
    239:"Twister",240:"Rain Dance",241:"Sunny Day",242:"Crunch",243:"Mirror Coat",
    244:"Psych Up",245:"Extreme Speed",246:"Ancient Power",247:"Shadow Ball",
    248:"Future Sight",249:"Rock Smash",250:"Whirlpool",251:"Beat Up",252:"Fake Out",
    253:"Uproar",254:"Stockpile",255:"Spit Up",256:"Swallow",257:"Heat Wave",
    258:"Hail",259:"Torment",260:"Flatter",261:"Will-O-Wisp",262:"Memento",
    263:"Facade",264:"Focus Punch",265:"Smelling Salts",266:"Follow Me",267:"Nature Power",
    268:"Charge",269:"Taunt",270:"Helping Hand",271:"Trick",272:"Role Play",
    273:"Wish",274:"Assist",275:"Ingrain",276:"Superpower",277:"Magic Coat",
    278:"Recycle",279:"Revenge",280:"Brick Break",281:"Yawn",282:"Knock Off",
    283:"Endeavor",284:"Eruption",285:"Skill Swap",286:"Imprison",287:"Refresh",
    288:"Grudge",289:"Snatch",290:"Secret Power",291:"Dive",292:"Arm Thrust",
    293:"Camouflage",294:"Tail Glow",295:"Luster Purge",296:"Mist Ball",
    297:"Feather Dance",298:"Teeter Dance",299:"Blaze Kick",300:"Mud Sport",
    301:"Ice Ball",302:"Needle Arm",303:"Slack Off",304:"Hyper Voice",305:"Poison Fang",
    306:"Crush Claw",307:"Blast Burn",308:"Hydro Cannon",309:"Meteor Mash",
    310:"Astonish",311:"Weather Ball",312:"Aromatherapy",313:"Fake Tears",
    314:"Air Cutter",315:"Overheat",316:"Odor Sleuth",317:"Rock Tomb",
    318:"Silver Wind",319:"Metal Sound",320:"Grass Whistle",321:"Tickle",
    322:"Cosmic Power",323:"Water Spout",324:"Signal Beam",325:"Shadow Punch",
    326:"Extrasensory",327:"Sky Uppercut",328:"Sand Tomb",329:"Sheer Cold",
    330:"Muddy Water",331:"Bullet Seed",332:"Aerial Ace",333:"Icicle Spear",
    334:"Iron Defense",335:"Block",336:"Howl",337:"Dragon Claw",338:"Frenzy Plant",
    339:"Bulk Up",340:"Bounce",341:"Mud Shot",342:"Poison Tail",343:"Covet",
    344:"Volt Tackle",345:"Magical Leaf",346:"Water Sport",347:"Calm Mind",
    348:"Leaf Blade",349:"Dragon Dance",350:"Rock Blast",351:"Shock Wave",
    352:"Water Pulse",353:"Doom Desire",354:"Psycho Boost",
}

# Gen 3 held items (partial)
GEN3_ITEMS = {
    0:"None",1:"Master Ball",2:"Ultra Ball",3:"Great Ball",4:"Poke Ball",
    5:"Safari Ball",6:"Net Ball",7:"Dive Ball",8:"Nest Ball",9:"Repeat Ball",
    10:"Timer Ball",11:"Luxury Ball",12:"Premier Ball",13:"Potion",14:"Antidote",
    15:"Burn Heal",16:"Ice Heal",17:"Awakening",18:"Parlyz Heal",19:"Full Restore",
    20:"Max Potion",21:"Hyper Potion",22:"Super Potion",23:"Full Heal",24:"Revive",
    25:"Max Revive",26:"Fresh Water",27:"Soda Pop",28:"Lemonade",29:"Moomoo Milk",
    30:"Energy Powder",31:"Energy Root",32:"Heal Powder",33:"Revival Herb",
    34:"Ether",35:"Max Ether",36:"Elixir",37:"Max Elixir",38:"Lava Cookie",
    39:"Blue Flute",40:"Yellow Flute",41:"Red Flute",42:"Black Flute",43:"White Flute",
    44:"Berry Juice",45:"Sacred Ash",46:"Shoal Salt",47:"Shoal Shell",48:"Red Shard",
    49:"Blue Shard",50:"Yellow Shard",51:"Green Shard",
    63:"HP Up",64:"Protein",65:"Iron",66:"Carbos",67:"Calcium",68:"Rare Candy",
    69:"PP Up",70:"Zinc",71:"PP Max",
    78:"Guard Spec.",79:"Dire Hit",80:"X Attack",81:"X Defend",82:"X Speed",
    83:"X Accuracy",84:"X Special",85:"Poke Doll",86:"Fluffy Tail",
    91:"Super Repel",92:"Max Repel",93:"Escape Rope",94:"Repel",
    103:"Sun Stone",104:"Moon Stone",105:"Fire Stone",106:"Thunder Stone",
    107:"Water Stone",108:"Leaf Stone",
    116:"TinyMushroom",117:"Big Mushroom",119:"Pearl",120:"Big Pearl",
    121:"Stardust",122:"Star Piece",123:"Nugget",124:"Heart Scale",
    131:"Orange Mail",132:"Harbor Mail",133:"Glitter Mail",134:"Mech Mail",
    135:"Wood Mail",136:"Wave Mail",137:"Bead Mail",138:"Shadow Mail",
    139:"Tropic Mail",140:"Dream Mail",141:"Fab Mail",142:"Retro Mail",
    143:"Cheri Berry",144:"Chesto Berry",145:"Pecha Berry",146:"Rawst Berry",
    147:"Aspear Berry",148:"Leppa Berry",149:"Oran Berry",150:"Persim Berry",
    151:"Lum Berry",152:"Sitrus Berry",153:"Figy Berry",154:"Wiki Berry",
    155:"Mago Berry",156:"Aguav Berry",157:"Iapapa Berry",158:"Razz Berry",
    159:"Bluk Berry",160:"Nanab Berry",161:"Wepear Berry",162:"Pinap Berry",
    163:"Pomeg Berry",164:"Kelpsy Berry",165:"Qualot Berry",166:"Hondew Berry",
    167:"Grepa Berry",168:"Tamato Berry",169:"Cornn Berry",170:"Magost Berry",
    171:"Rabuta Berry",172:"Nomel Berry",173:"Spelon Berry",174:"Pamtre Berry",
    175:"Watmel Berry",176:"Durin Berry",177:"Belue Berry",178:"Liechi Berry",
    179:"Ganlon Berry",180:"Salac Berry",181:"Petaya Berry",182:"Apicot Berry",
    183:"Lansat Berry",184:"Starf Berry",185:"Enigma Berry",
    216:"BrightPowder",217:"White Herb",218:"Macho Brace",219:"Exp. Share",
    220:"Quick Claw",221:"Soothe Bell",222:"Mental Herb",223:"Choice Band",
    224:"King's Rock",225:"Silver Powder",226:"Amulet Coin",227:"Cleanse Tag",
    228:"Soul Dew",229:"Deep Sea Tooth",230:"Deep Sea Scale",231:"Smoke Ball",
    232:"Everstone",233:"Focus Band",234:"Lucky Egg",235:"Scope Lens",
    236:"Metal Coat",237:"Leftovers",238:"Dragon Scale",239:"Light Ball",
    240:"Soft Sand",241:"Hard Stone",242:"Miracle Seed",243:"Black Glasses",
    244:"Black Belt",245:"Magnet",246:"Mystic Water",247:"Sharp Beak",
    248:"Poison Barb",249:"Never-Melt Ice",250:"Spell Tag",251:"Twisted Spoon",
    252:"Charcoal",253:"Dragon Fang",254:"Silk Scarf",255:"Up-Grade",
    256:"Shell Bell",257:"Sea Incense",258:"Lax Incense",259:"Lucky Punch",
    260:"Metal Powder",261:"Thick Club",262:"Stick",
}

# Met location names (Gen 3, partial)
GEN3_LOCATIONS = {
    0:"Fateful encounter",1:"Pallet Town",2:"Viridian City",3:"Pewter City",
    4:"Cerulean City",5:"Lavender Town",6:"Vermilion City",7:"Celadon City",
    8:"Fuchsia City",9:"Cinnabar Island",10:"Indigo Plateau",11:"Saffron City",
    12:"Route 1",13:"Route 2",14:"Route 3",15:"Route 4",16:"Route 5",
    17:"Route 6",18:"Route 7",19:"Route 8",20:"Route 9",21:"Route 10",
    22:"Route 11",23:"Route 12",24:"Route 13",25:"Route 14",26:"Route 15",
    27:"Route 16",28:"Route 17",29:"Route 18",30:"Route 19",31:"Route 20",
    32:"Route 21",33:"Route 22",34:"Route 23",35:"Route 24",36:"Route 25",
    37:"Viridian Forest",38:"Mt. Moon",39:"S.S. Anne",40:"Underground Path",
    41:"Underground Path",42:"Safari Zone",43:"Rock Tunnel",44:"Seafoam Islands",
    45:"Pokemon Tower",46:"Cerulean Cave",47:"Power Plant",48:"Pokemon Mansion",
    49:"Victory Road",50:"Trade",51:"Egg",
    # Hoenn locations
    200:"Littleroot Town",201:"Oldale Town",202:"Dewford Town",203:"Lavaridge Town",
    204:"Fallarbor Town",205:"Verdanturf Town",206:"Pacifidlog Town",207:"Petalburg City",
    208:"Slateport City",209:"Mauville City",210:"Rustboro City",211:"Fortree City",
    212:"Lilycove City",213:"Mossdeep City",214:"Sootopolis City",215:"Ever Grande City",
    216:"Route 101",217:"Route 102",218:"Route 103",219:"Route 104",220:"Route 105",
    221:"Route 106",222:"Route 107",223:"Route 108",224:"Route 109",225:"Route 110",
    226:"Route 111",227:"Route 112",228:"Route 113",229:"Route 114",230:"Route 115",
    231:"Route 116",232:"Route 117",233:"Route 118",234:"Route 119",235:"Route 120",
    236:"Route 121",237:"Route 122",238:"Route 123",239:"Route 124",240:"Route 125",
    241:"Route 126",242:"Route 127",243:"Route 128",244:"Route 129",245:"Route 130",
    246:"Route 131",247:"Route 132",248:"Route 133",249:"Route 134",
    250:"Petalburg Woods",251:"Rusturf Tunnel",252:"Granite Cave",253:"Mt. Chimney",
    254:"Jagged Pass",255:"Fiery Path",256:"Mt. Pyre",257:"Team Aqua Hideout",
    258:"Seafloor Cavern",259:"Cave of Origin",260:"Victory Road",261:"Shoal Cave",
    262:"New Mauville",263:"Sea Mauville",264:"Sky Pillar",265:"Battle Tower",
    266:"Safari Zone",267:"Mirage Island",268:"Desert Ruins",269:"Island Cave",
    270:"Ancient Tomb",271:"Artisan Cave",272:"Altering Cave",
}


# ── GBA Save Parser ────────────────────────────────────────────────────────────

class GBASaveParser:
    """
    Parser for Gen 3 GBA Pokemon save files (.sav).

    Handles Ruby, Sapphire, Emerald, FireRed, and LeafGreen.
    Implements the full Gen 3 save section structure and PK3 decryption.
    """

    def parse_save_file(self, file_path: str) -> Optional[GBASave]:
        """
        Parse a GBA .sav file.

        Args:
            file_path: Path to the .sav file

        Returns:
            GBASave on success, None on failure
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Save file not found: {file_path}")
            return None

        try:
            data = path.read_bytes()
        except OSError as e:
            logger.error(f"Cannot read save file: {e}")
            return None

        if len(data) < GBA_SAVE_SIZE:
            logger.warning(f"Save file smaller than expected: {len(data)} bytes (expected {GBA_SAVE_SIZE})")
            if len(data) < GBA_SLOT_SIZE:
                logger.error("Save file too small to parse")
                return None

        # Try both save slots, use the one with the higher save index
        slot_a = self._parse_slot(data, 0)
        slot_b = self._parse_slot(data, GBA_SLOT_SIZE) if len(data) >= GBA_SAVE_SIZE else None

        sections = self._pick_best_slot(slot_a, slot_b)
        if sections is None:
            logger.error("No valid save slot found")
            return None

        slot_used = 0 if sections is slot_a else 1

        # Parse trainer info from section 0
        info = self._parse_trainer_info(sections, file_path, slot_used)
        if info is None:
            return None

        # Parse party from section 1
        party = self._parse_party(sections)

        # Parse PC boxes from sections 5-13
        boxes = self._parse_pc_boxes(sections)

        return GBASave(info=info, party=party, boxes=boxes)

    def _parse_slot(self, data: bytes, offset: int) -> Optional[Dict[int, bytes]]:
        """
        Parse one save slot into a dict of {section_id: section_data}.
        Returns None if the slot is invalid.
        """
        sections = {}
        for i in range(GBA_SECTION_COUNT):
            section_start = offset + i * GBA_SECTION_SIZE
            section_end   = section_start + GBA_SECTION_SIZE
            if section_end > len(data):
                break
            section = data[section_start:section_end]

            # Read section ID from footer
            section_id = struct.unpack_from('<H', section, GBA_SECTION_ID_OFF)[0]
            if section_id > 13:
                continue  # Invalid section ID

            # Verify checksum
            if not self._verify_section_checksum(section):
                logger.debug(f"Section {section_id} checksum failed")

            sections[section_id] = section

        return sections if sections else None

    def _verify_section_checksum(self, section: bytes) -> bool:
        """Verify the checksum of a save section."""
        try:
            stored_checksum = struct.unpack_from('<H', section, GBA_CHECKSUM_OFF)[0]
            # Checksum covers first 0xFF8 bytes (data area)
            data_area = section[:GBA_FOOTER_OFFSET]
            # Sum all 32-bit words
            total = 0
            for i in range(0, len(data_area), 4):
                if i + 4 <= len(data_area):
                    total += struct.unpack_from('<I', data_area, i)[0]
            # Fold to 16 bits
            checksum = ((total >> 16) + (total & 0xFFFF)) & 0xFFFF
            return checksum == stored_checksum
        except struct.error:
            return False

    def _get_save_index(self, sections: Dict[int, bytes]) -> int:
        """Get the save index from section 0."""
        if 0 not in sections:
            return -1
        try:
            return struct.unpack_from('<I', sections[0], GBA_SAVE_INDEX_OFF)[0]
        except struct.error:
            return -1

    def _pick_best_slot(
        self,
        slot_a: Optional[Dict[int, bytes]],
        slot_b: Optional[Dict[int, bytes]],
    ) -> Optional[Dict[int, bytes]]:
        """Pick the save slot with the higher save index (most recent)."""
        if slot_a is None and slot_b is None:
            return None
        if slot_a is None:
            return slot_b
        if slot_b is None:
            return slot_a
        idx_a = self._get_save_index(slot_a)
        idx_b = self._get_save_index(slot_b)
        return slot_a if idx_a >= idx_b else slot_b

    def _read_gba_string(self, data: bytes, offset: int, max_len: int = 7) -> str:
        """
        Read a Gen 3 GBA character-encoded string.

        Gen 3 uses a custom character table (not ASCII).
        This implements the standard Gen 3 character map.
        """
        # Gen 3 character table (international)
        CHAR_TABLE = {
            0x00: ' ', 0xA1: '0', 0xA2: '1', 0xA3: '2', 0xA4: '3',
            0xA5: '4', 0xA6: '5', 0xA7: '6', 0xA8: '7', 0xA9: '8',
            0xAA: '9', 0xAB: '!', 0xAC: '?', 0xAD: '.', 0xAE: '-',
            0xB1: "'", 0xB2: "'", 0xB3: '"', 0xB4: '"', 0xB5: '…',
            0xB6: '>', 0xB7: '<', 0xB8: '=',
            0xBB: '/', 0xBC: 'A', 0xBD: 'B', 0xBE: 'C', 0xBF: 'D',
            0xC0: 'E', 0xC1: 'F', 0xC2: 'G', 0xC3: 'H', 0xC4: 'I',
            0xC5: 'J', 0xC6: 'K', 0xC7: 'L', 0xC8: 'M', 0xC9: 'N',
            0xCA: 'O', 0xCB: 'P', 0xCC: 'Q', 0xCD: 'R', 0xCE: 'S',
            0xCF: 'T', 0xD0: 'U', 0xD1: 'V', 0xD2: 'W', 0xD3: 'X',
            0xD4: 'Y', 0xD5: 'Z', 0xD6: '(', 0xD7: ')',
            0xD8: ':', 0xD9: ';', 0xDA: '[', 0xDB: ']',
            0xDC: 'a', 0xDD: 'b', 0xDE: 'c', 0xDF: 'd',
            0xE0: 'e', 0xE1: 'f', 0xE2: 'g', 0xE3: 'h', 0xE4: 'i',
            0xE5: 'j', 0xE6: 'k', 0xE7: 'l', 0xE8: 'm', 0xE9: 'n',
            0xEA: 'o', 0xEB: 'p', 0xEC: 'q', 0xED: 'r', 0xEE: 's',
            0xEF: 't', 0xF0: 'u', 0xF1: 'v', 0xF2: 'w', 0xF3: 'x',
            0xF4: 'y', 0xF5: 'z', 0xFF: '',  # String terminator
        }
        chars = []
        for i in range(max_len):
            if offset + i >= len(data):
                break
            byte = data[offset + i]
            if byte == 0xFF:  # String terminator
                break
            chars.append(CHAR_TABLE.get(byte, '?'))
        return ''.join(chars).strip()

    def _parse_trainer_info(
        self,
        sections: Dict[int, bytes],
        file_path: str,
        slot_used: int,
    ) -> Optional[GBASaveInfo]:
        """Parse trainer info from section 0."""
        if 0 not in sections:
            return None

        sec = sections[0]
        try:
            # Trainer name: 7 bytes at offset 0x00
            trainer_name = self._read_gba_string(sec, 0x00, 7)

            # Trainer ID: 2 bytes at 0x0A (public ID)
            trainer_id = struct.unpack_from('<H', sec, 0x0A)[0]

            # Secret ID: 2 bytes at 0x0C
            secret_id = struct.unpack_from('<H', sec, 0x0C)[0]

            # Play time: hours (2 bytes at 0x0E), minutes (1 byte at 0x10), seconds (1 byte at 0x11)
            play_h = struct.unpack_from('<H', sec, 0x0E)[0]
            play_m = sec[0x10]
            play_s = sec[0x11]

            # Money: 4 bytes at 0x0290 (encrypted with trainer ID in some games)
            money = struct.unpack_from('<I', sec, 0x0290)[0] if len(sec) > 0x0294 else 0

            # Badges: 1 byte at 0x0098 (Hoenn) or 0x00C5 (Kanto)
            badges = sec[0x0098] if len(sec) > 0x0098 else 0

            # Detect game from section data
            game, region = self._detect_game(sections)
            game_name = self._get_game_name(game, region)

            return GBASaveInfo(
                file_path=file_path,
                game=game,
                region=region,
                game_name=game_name,
                trainer_name=trainer_name or "Trainer",
                trainer_id=trainer_id,
                secret_id=secret_id,
                play_time_h=play_h,
                play_time_m=play_m,
                play_time_s=play_s,
                money=money,
                badges=bin(badges).count('1'),
                slot_used=slot_used,
            )
        except (struct.error, IndexError) as e:
            logger.error(f"Failed to parse trainer info: {e}")
            return None

    def _detect_game(self, sections: Dict[int, bytes]) -> Tuple[GBAGame, GBARegion]:
        """
        Detect which GBA game this save is from.
        Uses heuristics based on save structure differences.
        """
        # Check section 0 for game-specific markers
        if 0 not in sections:
            return GBAGame.UNKNOWN, GBARegion.UNKNOWN

        sec0 = sections[0]

        # Emerald has a different save structure (larger section 0 data)
        # FireRed/LeafGreen have Kanto-specific data
        # Ruby/Sapphire have Hoenn-specific data

        # Check for Emerald: has Battle Frontier data in section 0
        # Simple heuristic: check specific bytes that differ between games
        # In practice, you'd check the ROM header stored in the save

        # For now, use section count and data patterns
        if len(sections) == GBA_SECTION_COUNT:
            # Check for Emerald-specific data at offset 0xAC
            if len(sec0) > 0xAC and sec0[0xAC] != 0:
                return GBAGame.EMERALD, GBARegion.US

            # Check for FireRed/LeafGreen: Kanto badge data at 0x00C5
            if len(sec0) > 0x00C5 and sec0[0x00C5] != 0:
                # FR/LG have different badge byte location
                return GBAGame.FIRERED, GBARegion.US

        return GBAGame.RUBY, GBARegion.US  # Default assumption

    def _get_game_name(self, game: GBAGame, region: GBARegion) -> str:
        """Get human-readable game name."""
        names = {
            GBAGame.RUBY:      "Pokemon Ruby",
            GBAGame.SAPPHIRE:  "Pokemon Sapphire",
            GBAGame.EMERALD:   "Pokemon Emerald",
            GBAGame.FIRERED:   "Pokemon FireRed",
            GBAGame.LEAFGREEN: "Pokemon LeafGreen",
            GBAGame.UNKNOWN:   "Unknown GBA Game",
        }
        region_str = f" ({region.value.upper()})" if region != GBARegion.UNKNOWN else ""
        return names.get(game, "Unknown") + region_str

    def _parse_party(self, sections: Dict[int, bytes]) -> GBAParty:
        """Parse the party Pokemon from section 1."""
        if 1 not in sections:
            return GBAParty()

        sec = sections[1]
        try:
            count = struct.unpack_from('<I', sec, PARTY_COUNT_OFFSET)[0]
            count = max(0, min(6, count))
        except struct.error:
            return GBAParty()

        pokemon = []
        for i in range(count):
            offset = PARTY_DATA_OFFSET + i * PK3_SIZE
            if offset + PK3_SIZE > len(sec):
                break
            pk3_data = sec[offset:offset + PK3_SIZE]
            poke = self._parse_pk3(pk3_data)
            if poke and poke.species_id > 0:
                pokemon.append(poke)

        return GBAParty(pokemon=pokemon, count=len(pokemon))

    def _parse_pc_boxes(self, sections: Dict[int, bytes]) -> List[GBABox]:
        """Parse PC box data from sections 5-13."""
        # Reconstruct the PC buffer by concatenating sections 5-13
        pc_data = bytearray()
        for section_id in range(SECTION_PC_BUFFER_A, GBA_SECTION_COUNT):
            if section_id in sections:
                # Each section contributes its data area (first 0xFF8 bytes)
                pc_data.extend(sections[section_id][:GBA_FOOTER_OFFSET])

        if not pc_data:
            return []

        boxes = []
        # Box names start at offset 0x8344 in the PC buffer
        # Box data starts at offset 0x0004 in the PC buffer
        BOX_DATA_START  = 0x0004
        BOX_NAMES_START = 0x8344
        BOX_NAME_LEN    = 9

        for box_idx in range(PC_BOX_COUNT):
            # Read box name
            name_offset = BOX_NAMES_START + box_idx * BOX_NAME_LEN
            if name_offset + BOX_NAME_LEN <= len(pc_data):
                box_name = self._read_gba_string(pc_data, name_offset, BOX_NAME_LEN)
            else:
                box_name = f"Box {box_idx + 1}"

            if not box_name:
                box_name = f"Box {box_idx + 1}"

            # Read Pokemon in this box
            box_pokemon = []
            for slot in range(PC_BOX_SIZE):
                poke_offset = BOX_DATA_START + (box_idx * PC_BOX_SIZE + slot) * PC_POKEMON_SIZE
                if poke_offset + PC_POKEMON_SIZE > len(pc_data):
                    break
                pk3_data = bytes(pc_data[poke_offset:poke_offset + PC_POKEMON_SIZE])
                # PC Pokemon don't have status data — pad to full PK3 size
                pk3_padded = pk3_data + bytes(PK3_SIZE - PC_POKEMON_SIZE)
                poke = self._parse_pk3(pk3_padded)
                if poke and poke.species_id > 0:
                    box_pokemon.append(poke)

            boxes.append(GBABox(box_index=box_idx, name=box_name, pokemon=box_pokemon))

        return boxes

    def _parse_pk3(self, data: bytes) -> Optional[PK3Pokemon]:
        """
        Parse a single PK3 Pokemon from 100 bytes of raw data.

        The 48-byte data section is encrypted using:
            key = personality_value XOR (trainer_id | (secret_id << 16))
        """
        if len(data) < PK3_HEADER_SIZE:
            return None

        try:
            # ── Unencrypted header (32 bytes) ──────────────────────────────
            personality_value = struct.unpack_from('<I', data, 0x00)[0]
            ot_id_full        = struct.unpack_from('<I', data, 0x04)[0]
            ot_id             = ot_id_full & 0xFFFF
            ot_secret_id      = (ot_id_full >> 16) & 0xFFFF

            # Nickname: 10 bytes at 0x08
            nickname = self._read_gba_string(data, 0x08, 10)

            # Language: 1 byte at 0x12
            language = data[0x12] if len(data) > 0x12 else 2

            # OT name: 7 bytes at 0x14
            ot_name = self._read_gba_string(data, 0x14, 7)

            # Markings: 1 byte at 0x1B
            markings = data[0x1B] if len(data) > 0x1B else 0

            # Checksum: 2 bytes at 0x1C
            checksum = struct.unpack_from('<H', data, 0x1C)[0] if len(data) > 0x1E else 0

            # ── Decrypt the 48-byte data section ──────────────────────────
            if len(data) < PK3_HEADER_SIZE + PK3_DATA_SIZE:
                return None

            encrypted = data[PK3_HEADER_SIZE:PK3_HEADER_SIZE + PK3_DATA_SIZE]
            key = personality_value ^ ot_id_full
            decrypted = self._decrypt_pk3_data(encrypted, key)

            # ── Determine substructure order ───────────────────────────────
            order_idx = personality_value % 24
            order = SUBSTRUCTURE_ORDER[order_idx]

            # Map substructure letters to their 12-byte blocks
            sub_map = {}
            for i, letter in enumerate(order):
                sub_map[letter] = decrypted[i * 12:(i + 1) * 12]

            # ── Parse Growth substructure (G) ──────────────────────────────
            g = sub_map.get('G', bytes(12))
            species_id  = struct.unpack_from('<H', g, 0)[0]
            item_id     = struct.unpack_from('<H', g, 2)[0]
            experience  = struct.unpack_from('<I', g, 4)[0]
            pp_bonuses  = g[8]
            friendship  = g[9]
            unknown_g   = struct.unpack_from('<H', g, 10)[0]

            if species_id == 0 or species_id > 386:
                return None

            # ── Parse Attacks substructure (A) ─────────────────────────────
            a = sub_map.get('A', bytes(12))
            move1_id = struct.unpack_from('<H', a, 0)[0]
            move2_id = struct.unpack_from('<H', a, 2)[0]
            move3_id = struct.unpack_from('<H', a, 4)[0]
            move4_id = struct.unpack_from('<H', a, 6)[0]
            move1_pp = a[8]; move2_pp = a[9]; move3_pp = a[10]; move4_pp = a[11]

            # ── Parse EVs/Condition substructure (E) ───────────────────────
            e = sub_map.get('E', bytes(12))
            hp_ev  = e[0]; atk_ev = e[1]; def_ev = e[2]
            spe_ev = e[3]; spa_ev = e[4]; spd_ev = e[5]
            coolness   = e[6]; beauty    = e[7]; cuteness  = e[8]
            smartness  = e[9]; toughness = e[10]; feel     = e[11]

            # ── Parse Misc substructure (M) ────────────────────────────────
            m = sub_map.get('M', bytes(12))
            pokerus           = m[0]
            met_location      = m[1]
            origins_info      = struct.unpack_from('<H', m, 2)[0]
            iv_egg_ability    = struct.unpack_from('<I', m, 4)[0]
            ribbons_obedience = struct.unpack_from('<I', m, 8)[0]

            # ── Parse Status data (unencrypted, last 20 bytes) ─────────────
            status_offset = PK3_HEADER_SIZE + PK3_DATA_SIZE
            if len(data) >= status_offset + PK3_STATUS_SIZE:
                st = data[status_offset:status_offset + PK3_STATUS_SIZE]
                status_condition = struct.unpack_from('<I', st, 0)[0]
                level            = st[4]
                pokerus_days     = st[5]
                current_hp       = struct.unpack_from('<H', st, 6)[0]
                total_hp         = struct.unpack_from('<H', st, 8)[0]
                attack           = struct.unpack_from('<H', st, 10)[0]
                defense          = struct.unpack_from('<H', st, 12)[0]
                speed            = struct.unpack_from('<H', st, 14)[0]
                sp_attack        = struct.unpack_from('<H', st, 16)[0]
                sp_defense       = struct.unpack_from('<H', st, 18)[0]
            else:
                # PC Pokemon — calculate level from experience
                status_condition = 0; level = self._exp_to_level(species_id, experience)
                pokerus_days = 0; current_hp = 0; total_hp = 0
                attack = 0; defense = 0; speed = 0; sp_attack = 0; sp_defense = 0

            # ── Derive computed fields ─────────────────────────────────────
            nature = NATURES[personality_value % 25]

            # IVs packed in iv_egg_ability (30 bits)
            hp_iv  = (iv_egg_ability >>  0) & 0x1F
            atk_iv = (iv_egg_ability >>  5) & 0x1F
            def_iv = (iv_egg_ability >> 10) & 0x1F
            spe_iv = (iv_egg_ability >> 15) & 0x1F
            spa_iv = (iv_egg_ability >> 20) & 0x1F
            spd_iv = (iv_egg_ability >> 25) & 0x1F

            is_egg     = bool((iv_egg_ability >> 30) & 1)
            ability_sl = (iv_egg_ability >> 31) & 1

            # Shiny check: (ot_id XOR ot_secret_id XOR (pv >> 16) XOR (pv & 0xFFFF)) < 8
            pv_high = (personality_value >> 16) & 0xFFFF
            pv_low  = personality_value & 0xFFFF
            shiny_val = ot_id ^ ot_secret_id ^ pv_high ^ pv_low
            is_shiny = shiny_val < 8

            # Gender from personality value (species-dependent, simplified)
            gender = self._calc_gender(species_id, personality_value)

            # Met game from origins_info bits 7-10
            met_game_id = (origins_info >> 7) & 0xF
            met_game = self._origins_to_game(met_game_id)

            # Met level from origins_info bits 0-6
            met_level = origins_info & 0x7F

            # Fateful encounter flag
            is_fateful = bool((ribbons_obedience >> 31) & 1)

            # Move names
            move_names = []
            for mid in [move1_id, move2_id, move3_id, move4_id]:
                if mid > 0:
                    move_names.append(GEN3_MOVES.get(mid, f"Move #{mid}"))

            species_name = GEN3_SPECIES.get(species_id, f"Pokemon #{species_id}")
            item_name    = GEN3_ITEMS.get(item_id, f"Item #{item_id}" if item_id > 0 else "None")

            return PK3Pokemon(
                personality_value=personality_value,
                ot_id=ot_id, ot_secret_id=ot_secret_id,
                nickname=nickname or species_name,
                language=language, ot_name=ot_name or "Trainer",
                markings=markings, checksum=checksum,
                species_id=species_id, item_id=item_id,
                experience=experience, pp_bonuses=pp_bonuses,
                friendship=friendship, unknown_growth=unknown_g,
                move1_id=move1_id, move2_id=move2_id,
                move3_id=move3_id, move4_id=move4_id,
                move1_pp=move1_pp, move2_pp=move2_pp,
                move3_pp=move3_pp, move4_pp=move4_pp,
                hp_ev=hp_ev, atk_ev=atk_ev, def_ev=def_ev,
                spe_ev=spe_ev, spa_ev=spa_ev, spd_ev=spd_ev,
                coolness=coolness, beauty=beauty, cuteness=cuteness,
                smartness=smartness, toughness=toughness, feel=feel,
                pokerus=pokerus, met_location=met_location,
                origins_info=origins_info, iv_egg_ability=iv_egg_ability,
                ribbons_obedience=ribbons_obedience,
                status_condition=status_condition, level=level,
                pokerus_days=pokerus_days, current_hp=current_hp,
                total_hp=total_hp, attack=attack, defense=defense,
                speed=speed, sp_attack=sp_attack, sp_defense=sp_defense,
                # Derived
                species_name=species_name, nature=nature,
                is_shiny=is_shiny, is_egg=is_egg, gender=gender,
                ability_slot=ability_sl,
                hp_iv=hp_iv, atk_iv=atk_iv, def_iv=def_iv,
                spe_iv=spe_iv, spa_iv=spa_iv, spd_iv=spd_iv,
                move_names=move_names, item_name=item_name,
                met_game=met_game, met_level=met_level,
                is_fateful=is_fateful,
            )

        except (struct.error, IndexError) as e:
            logger.debug(f"PK3 parse error: {e}")
            return None

    def _decrypt_pk3_data(self, encrypted: bytes, key: int) -> bytes:
        """Decrypt the 48-byte PK3 data section using XOR with the key."""
        decrypted = bytearray(len(encrypted))
        # The key is applied as a 32-bit XOR, cycling through the data
        for i in range(0, len(encrypted), 4):
            if i + 4 <= len(encrypted):
                word = struct.unpack_from('<I', encrypted, i)[0]
                word ^= key
                struct.pack_into('<I', decrypted, i, word)
        return bytes(decrypted)

    def _exp_to_level(self, species_id: int, experience: int) -> int:
        """Estimate level from experience (simplified — uses medium-fast formula)."""
        if experience <= 0:
            return 1
        # Medium-fast: exp = level^3
        level = int(experience ** (1/3))
        return max(1, min(100, level))

    def _calc_gender(self, species_id: int, personality_value: int) -> str:
        """
        Calculate gender from personality value.
        Uses simplified gender ratios (not species-specific).
        """
        # Gender threshold from personality value low byte
        pv_low = personality_value & 0xFF
        # Most Pokemon: 0x7F threshold (50/50), 0x1F (87.5% male), etc.
        # Simplified: use 0x7F as default threshold
        if pv_low < 0x7F:
            return "male"
        elif pv_low == 0xFF:
            return "unknown"  # Genderless
        else:
            return "female"

    def _origins_to_game(self, game_id: int) -> str:
        """Convert origins_info game ID to game name."""
        origins = {
            1: "Sapphire", 2: "Ruby", 3: "Emerald",
            4: "FireRed", 5: "LeafGreen",
            15: "Colosseum/XD",
        }
        return origins.get(game_id, f"Game {game_id}")


# ── GBA→GCN Transfer System ────────────────────────────────────────────────────

class GBAToGCNTransfer:
    """
    Handles the GBA→GameCube link cable transfer system.

    In the original games, this worked via:
    1. GBA connected to GameCube via official link cable
    2. Colosseum/XD reads GBA party and boxes
    3. Player selects Pokemon to trade
    4. Pokemon is converted from PK3 to GCN format
    5. Shadow Pokemon can be traded back to GBA after purification

    PTB simulates this by:
    - Parsing GBA .sav files
    - Validating Pokemon for GCN compatibility
    - Converting PK3 data to PTB's internal format
    """

    def __init__(self):
        self._parser = GBASaveParser()

    def load_gba_save(self, file_path: str) -> Optional[GBASave]:
        """Load and parse a GBA save file."""
        return self._parser.parse_save_file(file_path)

    def get_transferable_pokemon(self, save: GBASave) -> List[Tuple[str, PK3Pokemon]]:
        """
        Get all Pokemon that can be transferred to GCN.

        Returns:
            List of (location, PK3Pokemon) tuples where location is
            "party", "box_N", etc.
        """
        result = []

        for i, poke in enumerate(save.party.pokemon):
            if poke.transfer_compatibility == TransferCompatibility.COMPATIBLE:
                result.append((f"party_{i}", poke))

        for box in save.boxes:
            for i, poke in enumerate(box.pokemon):
                if poke.transfer_compatibility == TransferCompatibility.COMPATIBLE:
                    result.append((f"box_{box.box_index}_{i}", poke))

        return result

    def check_transfer_compatibility(
        self,
        pokemon: PK3Pokemon,
        target_game: str = "colosseum",
    ) -> Tuple[TransferCompatibility, str]:
        """
        Check if a Pokemon can be transferred to a specific GCN game.

        Args:
            pokemon:     The Pokemon to check
            target_game: "colosseum" or "xd_gale"

        Returns:
            (compatibility, reason) tuple
        """
        if pokemon.is_egg:
            return TransferCompatibility.INCOMPATIBLE, "Eggs cannot be transferred"

        if pokemon.species_id == 0 or pokemon.species_id > 386:
            return TransferCompatibility.INCOMPATIBLE, "Invalid species"

        # Check for hacked/illegal Pokemon (basic checks)
        if pokemon.level > 100 or pokemon.level < 1:
            return TransferCompatibility.INCOMPATIBLE, "Invalid level"

        total_evs = (pokemon.hp_ev + pokemon.atk_ev + pokemon.def_ev +
                     pokemon.spe_ev + pokemon.spa_ev + pokemon.spd_ev)
        if total_evs > 510:
            return TransferCompatibility.INCOMPATIBLE, "EVs exceed maximum (510)"

        # All Gen 1-3 Pokemon are compatible with Colosseum/XD
        return TransferCompatibility.COMPATIBLE, "Compatible"

    def convert_pk3_to_ptb_dict(self, pokemon: PK3Pokemon) -> Dict[str, Any]:
        """
        Convert a PK3Pokemon to PTB's internal team builder format.

        This is the bridge between GBA save data and PTB's Pokemon class.
        """
        return {
            'name':       pokemon.nickname or pokemon.species_name,
            'species_id': pokemon.species_id,
            'level':      pokemon.level,
            'nature':     pokemon.nature.lower(),
            'ability':    '',  # Ability slot known but name requires lookup
            'is_shiny':   pokemon.is_shiny,
            'gender':     pokemon.gender,
            'moves':      pokemon.move_names,
            'item':       pokemon.item_name if pokemon.item_name != "None" else None,
            'base_stats': {
                'hp': 0, 'attack': 0, 'defense': 0,
                'special_attack': 0, 'special_defense': 0, 'speed': 0,
            },
            'evs': {
                'hp': pokemon.hp_ev, 'attack': pokemon.atk_ev,
                'defense': pokemon.def_ev, 'special_attack': pokemon.spa_ev,
                'special_defense': pokemon.spd_ev, 'speed': pokemon.spe_ev,
            },
            'ivs': {
                'hp': pokemon.hp_iv, 'attack': pokemon.atk_iv,
                'defense': pokemon.def_iv, 'special_attack': pokemon.spa_iv,
                'special_defense': pokemon.spd_iv, 'speed': pokemon.spe_iv,
            },
            'ot_name':    pokemon.ot_name,
            'ot_id':      pokemon.ot_id,
            'met_game':   pokemon.met_game,
            'met_level':  pokemon.met_level,
            'friendship': pokemon.friendship,
            'is_fateful': pokemon.is_fateful,
            'game_era':   'gamecube',
            'status':     'normal',
            'is_shadow':  False,
        }

    def get_version_exclusives_info(self, game: GBAGame) -> Dict[str, Any]:
        """Get version-exclusive Pokemon info for a GBA game."""
        exclusives = {
            GBAGame.RUBY:      RUBY_EXCLUSIVES,
            GBAGame.SAPPHIRE:  SAPPHIRE_EXCLUSIVES,
            GBAGame.FIRERED:   FIRERED_EXCLUSIVES,
            GBAGame.LEAFGREEN: LEAFGREEN_EXCLUSIVES,
            GBAGame.EMERALD:   set(),  # Emerald has no version exclusives
        }
        exclusive_ids = exclusives.get(game, set())
        return {
            'game':      game.value,
            'exclusives': [
                {'id': sid, 'name': GEN3_SPECIES.get(sid, f"#{sid}")}
                for sid in sorted(exclusive_ids)
            ],
        }

    def get_colosseum_shadow_list(self) -> List[Dict[str, Any]]:
        """Get the list of Shadow Pokemon available in Colosseum."""
        # Colosseum Shadow Pokemon with their trainers
        shadow_list = [
            {'species_id': 37,  'name': 'Vulpix',     'trainer': 'Miror B.'},
            {'species_id': 52,  'name': 'Meowth',     'trainer': 'Miror B.'},
            {'species_id': 58,  'name': 'Growlithe',  'trainer': 'Miror B.'},
            {'species_id': 83,  'name': "Farfetch'd", 'trainer': 'Miror B.'},
            {'species_id': 85,  'name': 'Dodrio',     'trainer': 'Miror B.'},
            {'species_id': 86,  'name': 'Seel',       'trainer': 'Miror B.'},
            {'species_id': 87,  'name': 'Dewgong',    'trainer': 'Miror B.'},
            {'species_id': 88,  'name': 'Grimer',     'trainer': 'Miror B.'},
            {'species_id': 89,  'name': 'Muk',        'trainer': 'Miror B.'},
            {'species_id': 90,  'name': 'Shellder',   'trainer': 'Miror B.'},
            {'species_id': 91,  'name': 'Cloyster',   'trainer': 'Miror B.'},
            {'species_id': 92,  'name': 'Gastly',     'trainer': 'Miror B.'},
            {'species_id': 93,  'name': 'Haunter',    'trainer': 'Miror B.'},
            {'species_id': 94,  'name': 'Gengar',     'trainer': 'Miror B.'},
            {'species_id': 95,  'name': 'Onix',       'trainer': 'Miror B.'},
            {'species_id': 96,  'name': 'Drowzee',    'trainer': 'Miror B.'},
            {'species_id': 97,  'name': 'Hypno',      'trainer': 'Miror B.'},
            {'species_id': 100, 'name': 'Voltorb',    'trainer': 'Cipher Peon'},
            {'species_id': 101, 'name': 'Electrode',  'trainer': 'Cipher Peon'},
            {'species_id': 102, 'name': 'Exeggcute',  'trainer': 'Cipher Peon'},
            {'species_id': 103, 'name': 'Exeggutor',  'trainer': 'Cipher Peon'},
            {'species_id': 104, 'name': 'Cubone',     'trainer': 'Cipher Peon'},
            {'species_id': 105, 'name': 'Marowak',    'trainer': 'Cipher Peon'},
            {'species_id': 106, 'name': 'Hitmonlee',  'trainer': 'Cipher Peon'},
            {'species_id': 107, 'name': 'Hitmonchan', 'trainer': 'Cipher Peon'},
            {'species_id': 108, 'name': 'Lickitung',  'trainer': 'Cipher Peon'},
            {'species_id': 109, 'name': 'Koffing',    'trainer': 'Cipher Peon'},
            {'species_id': 110, 'name': 'Weezing',    'trainer': 'Cipher Peon'},
            {'species_id': 111, 'name': 'Rhyhorn',    'trainer': 'Cipher Peon'},
            {'species_id': 112, 'name': 'Rhydon',     'trainer': 'Cipher Peon'},
            {'species_id': 113, 'name': 'Chansey',    'trainer': 'Cipher Peon'},
            {'species_id': 114, 'name': 'Tangela',    'trainer': 'Cipher Peon'},
            {'species_id': 115, 'name': 'Kangaskhan', 'trainer': 'Cipher Peon'},
            {'species_id': 116, 'name': 'Horsea',     'trainer': 'Cipher Peon'},
            {'species_id': 117, 'name': 'Seadra',     'trainer': 'Cipher Peon'},
            {'species_id': 118, 'name': 'Goldeen',    'trainer': 'Cipher Peon'},
            {'species_id': 119, 'name': 'Seaking',    'trainer': 'Cipher Peon'},
            {'species_id': 120, 'name': 'Staryu',     'trainer': 'Cipher Peon'},
            {'species_id': 121, 'name': 'Starmie',    'trainer': 'Cipher Peon'},
            {'species_id': 122, 'name': 'Mr. Mime',   'trainer': 'Cipher Peon'},
            {'species_id': 123, 'name': 'Scyther',    'trainer': 'Cipher Peon'},
            {'species_id': 124, 'name': 'Jynx',       'trainer': 'Cipher Peon'},
            {'species_id': 125, 'name': 'Electabuzz', 'trainer': 'Cipher Peon'},
            {'species_id': 126, 'name': 'Magmar',     'trainer': 'Cipher Peon'},
            {'species_id': 127, 'name': 'Pinsir',     'trainer': 'Cipher Peon'},
            {'species_id': 128, 'name': 'Tauros',     'trainer': 'Cipher Peon'},
            {'species_id': 131, 'name': 'Lapras',     'trainer': 'Cipher Peon'},
            {'species_id': 137, 'name': 'Porygon',    'trainer': 'Cipher Peon'},
            {'species_id': 143, 'name': 'Snorlax',    'trainer': 'Cipher Peon'},
            {'species_id': 196, 'name': 'Espeon',     'trainer': 'Cipher Admin Dakim'},
            {'species_id': 197, 'name': 'Umbreon',    'trainer': 'Cipher Admin Venus'},
            {'species_id': 243, 'name': 'Raikou',     'trainer': 'Cipher Admin Ein'},
            {'species_id': 244, 'name': 'Entei',      'trainer': 'Cipher Admin Dakim'},
            {'species_id': 245, 'name': 'Suicune',    'trainer': 'Cipher Admin Venus'},
        ]
        return shadow_list

    def get_xd_shadow_list(self) -> List[Dict[str, Any]]:
        """Get the list of Shadow Pokemon available in XD: Gale of Darkness."""
        # XD has 83 Shadow Pokemon
        xd_list = [
            {'species_id': 16,  'name': 'Pidgey',      'trainer': 'Cipher Peon'},
            {'species_id': 17,  'name': 'Pidgeotto',   'trainer': 'Cipher Peon'},
            {'species_id': 18,  'name': 'Pidgeot',     'trainer': 'Cipher Peon'},
            {'species_id': 21,  'name': 'Spearow',     'trainer': 'Cipher Peon'},
            {'species_id': 22,  'name': 'Fearow',      'trainer': 'Cipher Peon'},
            {'species_id': 25,  'name': 'Pikachu',     'trainer': 'Cipher Peon'},
            {'species_id': 26,  'name': 'Raichu',      'trainer': 'Cipher Peon'},
            {'species_id': 27,  'name': 'Sandshrew',   'trainer': 'Cipher Peon'},
            {'species_id': 28,  'name': 'Sandslash',   'trainer': 'Cipher Peon'},
            {'species_id': 35,  'name': 'Clefairy',    'trainer': 'Cipher Peon'},
            {'species_id': 36,  'name': 'Clefable',    'trainer': 'Cipher Peon'},
            {'species_id': 39,  'name': 'Jigglypuff',  'trainer': 'Cipher Peon'},
            {'species_id': 40,  'name': 'Wigglytuff',  'trainer': 'Cipher Peon'},
            {'species_id': 41,  'name': 'Zubat',       'trainer': 'Cipher Peon'},
            {'species_id': 42,  'name': 'Golbat',      'trainer': 'Cipher Peon'},
            {'species_id': 54,  'name': 'Psyduck',     'trainer': 'Cipher Peon'},
            {'species_id': 55,  'name': 'Golduck',     'trainer': 'Cipher Peon'},
            {'species_id': 60,  'name': 'Poliwag',     'trainer': 'Cipher Peon'},
            {'species_id': 61,  'name': 'Poliwhirl',   'trainer': 'Cipher Peon'},
            {'species_id': 62,  'name': 'Poliwrath',   'trainer': 'Cipher Peon'},
            {'species_id': 63,  'name': 'Abra',        'trainer': 'Cipher Peon'},
            {'species_id': 64,  'name': 'Kadabra',     'trainer': 'Cipher Peon'},
            {'species_id': 65,  'name': 'Alakazam',    'trainer': 'Cipher Peon'},
            {'species_id': 66,  'name': 'Machop',      'trainer': 'Cipher Peon'},
            {'species_id': 67,  'name': 'Machoke',     'trainer': 'Cipher Peon'},
            {'species_id': 68,  'name': 'Machamp',     'trainer': 'Cipher Peon'},
            {'species_id': 72,  'name': 'Tentacool',   'trainer': 'Cipher Peon'},
            {'species_id': 73,  'name': 'Tentacruel',  'trainer': 'Cipher Peon'},
            {'species_id': 74,  'name': 'Geodude',     'trainer': 'Cipher Peon'},
            {'species_id': 75,  'name': 'Graveler',    'trainer': 'Cipher Peon'},
            {'species_id': 76,  'name': 'Golem',       'trainer': 'Cipher Peon'},
            {'species_id': 77,  'name': 'Ponyta',      'trainer': 'Cipher Peon'},
            {'species_id': 78,  'name': 'Rapidash',    'trainer': 'Cipher Peon'},
            {'species_id': 79,  'name': 'Slowpoke',    'trainer': 'Cipher Peon'},
            {'species_id': 80,  'name': 'Slowbro',     'trainer': 'Cipher Peon'},
            {'species_id': 81,  'name': 'Magnemite',   'trainer': 'Cipher Peon'},
            {'species_id': 82,  'name': 'Magneton',    'trainer': 'Cipher Peon'},
            {'species_id': 84,  'name': 'Doduo',       'trainer': 'Cipher Peon'},
            {'species_id': 98,  'name': 'Krabby',      'trainer': 'Cipher Peon'},
            {'species_id': 99,  'name': 'Kingler',     'trainer': 'Cipher Peon'},
            {'species_id': 129, 'name': 'Magikarp',    'trainer': 'Cipher Peon'},
            {'species_id': 130, 'name': 'Gyarados',    'trainer': 'Cipher Peon'},
            {'species_id': 132, 'name': 'Ditto',       'trainer': 'Cipher Peon'},
            {'species_id': 133, 'name': 'Eevee',       'trainer': 'Cipher Peon'},
            {'species_id': 134, 'name': 'Vaporeon',    'trainer': 'Cipher Peon'},
            {'species_id': 135, 'name': 'Jolteon',     'trainer': 'Cipher Peon'},
            {'species_id': 136, 'name': 'Flareon',     'trainer': 'Cipher Peon'},
            {'species_id': 138, 'name': 'Omanyte',     'trainer': 'Cipher Peon'},
            {'species_id': 139, 'name': 'Omastar',     'trainer': 'Cipher Peon'},
            {'species_id': 140, 'name': 'Kabuto',      'trainer': 'Cipher Peon'},
            {'species_id': 141, 'name': 'Kabutops',    'trainer': 'Cipher Peon'},
            {'species_id': 142, 'name': 'Aerodactyl',  'trainer': 'Cipher Peon'},
            {'species_id': 144, 'name': 'Articuno',    'trainer': 'Cipher Admin Ardos'},
            {'species_id': 145, 'name': 'Zapdos',      'trainer': 'Cipher Admin Eldes'},
            {'species_id': 146, 'name': 'Moltres',     'trainer': 'Cipher Admin Greevil'},
            {'species_id': 147, 'name': 'Dratini',     'trainer': 'Cipher Peon'},
            {'species_id': 148, 'name': 'Dragonair',   'trainer': 'Cipher Peon'},
            {'species_id': 149, 'name': 'Dragonite',   'trainer': 'Cipher Admin Greevil'},
            {'species_id': 150, 'name': 'Mewtwo',      'trainer': 'Cipher Admin Greevil'},
            {'species_id': 249, 'name': 'Lugia',       'trainer': 'Grand Master Greevil'},
        ]
        return xd_list
