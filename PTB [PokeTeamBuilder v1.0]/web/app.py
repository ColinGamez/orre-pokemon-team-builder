"""
PTB — Pokémon Team Builder v1.0
Flask Web Application
"""

import sys
import os
import json
import logging
import secrets
import functools
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# ── Path Setup ────────────────────────────────────────────────────────────────
# Add project root and src to Python path
_web_dir     = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_web_dir)
for _p in [_project_root, os.path.join(_project_root, 'src')]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room

try:
    from core.pokemon import Pokemon
    from core.types import PokemonType
    from teambuilder.team import PokemonTeam
    from teambuilder.analyzer import TeamAnalyzer
    from features.breeding_calculator import BreedingCalculator
    from features.tournament_system import TournamentManager, TournamentFormat
    from battle.battle_engine import BattleEngine
except ImportError:
    # Mock classes for when modules are not available
    class Pokemon:
        def __init__(self, name="MockPokemon", **kwargs):
            self.name = name
    class PokemonType:
        NORMAL = "normal"
    class PokemonTeam:
        def __init__(self, name="MockTeam"):
            self.name = name
    class TeamAnalyzer:
        def analyze_team(self, team):
            return {"coverage": "Good"}
    class BreedingCalculator:
        def calculate_breeding_path(self, pokemon):
            return {"steps": ["Mock step"]}
    class TournamentManager:
        def create_tournament(self, name, format):
            return {"id": "mock", "name": name}
    class TournamentFormat:
        SINGLE_ELIMINATION = "single_elimination"
    class BattleEngine:
        def create_battle(self, team1, team2):
            return {"id": "mock_battle"}

# Import GBA Support
try:
    from src.features.gba_support import GBASaveParser, GBAToGCNTransfer, GBAGame
    from src.trading.gba_trading import GBALinkCableTrading, GBALinkStatus
    gba_parser = GBASaveParser()
    gba_transfer = GBAToGCNTransfer()
except ImportError as _e2:
    gba_parser = None
    gba_transfer = None
    logging.getLogger(__name__).warning(f"GBA module not available: {_e2}")

# Import Memory Card support
try:
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.features.memory_card import MemoryCardManager, MemoryCard, MemoryCardGame, SlotStatus
    memory_card_manager = MemoryCardManager()
except ImportError as _e:
    memory_card_manager = None
    logging.getLogger(__name__).warning(f"Memory card module not available: {_e}")

# Import multiplayer components
from multiplayer_integration import WebMultiplayerIntegration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('PTB_SECRET_KEY', secrets.token_urlsafe(32))
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Enable CORS for API endpoints
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize SocketIO for real-time features
socketio = SocketIO(app, cors_allowed_origins="*")

# Global managers
tournament_manager = TournamentManager()
breeding_calculator = BreedingCalculator()
team_analyzer = TeamAnalyzer()
battle_engine = BattleEngine()

# Initialize multiplayer integration
multiplayer_integration = WebMultiplayerIntegration(app, socketio)

# In-memory storage (in production, use a proper database)
users_db = {}
teams_db = {}
battles_db = {}

class WebUser:
    """Web application user."""
    
    def __init__(self, username: str, email: str = ""):
        self.id = f"user_{len(users_db) + 1}"
        self.username = username
        self.email = email
        self.teams = []
        self.created_at = datetime.now()
        self.last_active = datetime.now()
        self.rating = 1000
        self.wins = 0
        self.losses = 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'rating': self.rating,
            'wins': self.wins,
            'losses': self.losses,
            'teams_count': len(self.teams),
            'created_at': self.created_at.isoformat(),
            'last_active': self.last_active.isoformat()
        }

def get_current_user():
    """Get current user from session."""
    if 'user_id' in session:
        return users_db.get(session['user_id'])
    return None

def require_login(f):
    """Decorator to require user login."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes

@app.route('/')
def index():
    """Main page."""
    user = get_current_user()
    try:
        active_tournaments = tournament_manager.get_active_tournaments()
    except Exception:
        active_tournaments = []
    return render_template('index.html', user=user, users_db=users_db, teams_db=teams_db, battles_db=battles_db, active_tournaments=active_tournaments)

# Multiplayer routes are now handled by multiplayer_integration

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        
        if not username:
            flash('Username is required', 'error')
            return render_template('login.html')
        
        # Find or create user
        user = None
        for u in users_db.values():
            if u.username == username:
                user = u
                break
        
        if not user:
            user = WebUser(username)
            users_db[user.id] = user
        
        user.last_active = datetime.now()
        session['user_id'] = user.id
        session['username'] = user.username
        
        flash(f'Welcome, {username}!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """User logout."""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@require_login
def dashboard():
    """User dashboard."""
    user = get_current_user()
    
    # Get user's teams
    user_teams = [teams_db[team_id] for team_id in user.teams if team_id in teams_db]
    
    # Get recent battles
    recent_battles = []
    for battle in battles_db.values():
        if user.id in [battle.get('player1_id'), battle.get('player2_id')]:
            recent_battles.append(battle)
    
    recent_battles = sorted(recent_battles, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
    
    return render_template('dashboard.html', 
                         user=user, 
                         teams=user_teams, 
                         recent_battles=recent_battles)

@app.route('/team-builder')
@require_login
def team_builder():
    """Team builder interface."""
    return render_template('team_builder.html')

@app.route('/teams')
@require_login
def teams():
    """Teams management page."""
    user = get_current_user()
    user_teams = [teams_db[team_id] for team_id in user.teams if team_id in teams_db]
    return render_template('teams.html', teams=user_teams)

@app.route('/tournaments')
def tournaments():
    """Tournaments page."""
    active_tournaments = tournament_manager.get_active_tournaments()
    completed_tournaments = tournament_manager.get_completed_tournaments()
    
    return render_template('tournaments.html',
                         active_tournaments=active_tournaments,
                         completed_tournaments=completed_tournaments)

@app.route('/breeding')
@require_login
def breeding():
    """Breeding calculator page."""
    return render_template('breeding.html')

@app.route('/battle')
@require_login
def battle():
    """Battle simulator page."""
    return render_template('battle.html')

@app.route('/leaderboard')
def leaderboard():
    """Global leaderboard page."""
    # Sort users by rating
    top_users = sorted(users_db.values(), key=lambda u: u.rating, reverse=True)[:50]
    return render_template('leaderboard.html', users=top_users)

# GBA Link Cable Routes

@app.route("/gba")
def gba_support():
    """GBA link cable support page."""
    return render_template("gba_support.html")

@app.route("/api/gba/import-save", methods=["POST"])
def api_gba_import_save():
    """Import a GBA .sav file."""
    if not gba_parser:
        return jsonify({"success": False, "error": "GBA module unavailable"}), 503
    if "sav_file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    f = request.files["sav_file"]
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".sav", delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name
    try:
        save = gba_parser.parse_save_file(tmp_path)
        if save is None:
            return jsonify({"success": False, "error": "Failed to parse GBA save file"}), 400
        import uuid as _uuid
        session_id = str(_uuid.uuid4())
        return jsonify({"success": True, "save": save.to_dict(), "session_id": session_id})
    finally:
        os.unlink(tmp_path)

@app.route("/api/gba/transfer-to-gcn", methods=["POST"])
def api_gba_transfer_to_gcn():
    """Transfer a Pokemon from GBA to GCN."""
    if not gba_transfer:
        return jsonify({"success": False, "error": "GBA module unavailable"}), 503
    data = request.get_json() or {}
    pokemon = data.get("pokemon", {})
    session_id = data.get("session_id", "")
    compat, reason = gba_transfer._checker.check_gba_to_gcn(
        species_id=pokemon.get("species_id", 0),
        is_shadow=False,
        is_egg=pokemon.get("is_egg", False),
        level=pokemon.get("level", 1),
        total_evs=sum([pokemon.get(k, 0) for k in ["hp_ev","atk_ev","def_ev","spe_ev","spa_ev","spd_ev"]]),
    )
    return jsonify({"success": compat, "result": "success" if compat else "failed", "error": None if compat else reason})

@app.route("/api/gba/convert-to-ptb", methods=["POST"])
def api_gba_convert_to_ptb():
    """Convert a PK3 Pokemon to PTB team builder format."""
    if not gba_transfer:
        return jsonify({"success": False, "error": "GBA module unavailable"}), 503
    data = request.get_json() or {}
    pokemon_data = data.get("pokemon", {})
    try:
        from src.features.gba_support import PK3Pokemon
        pk3 = PK3Pokemon.from_dict(pokemon_data)
        ptb_data = gba_transfer.convert_pk3_to_ptb_dict(pk3)
        return jsonify({"success": True, "ptb_pokemon": ptb_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/gba/shadow-list")
def api_gba_shadow_list():
    """Get Shadow Pokemon list for Colosseum or XD."""
    if not gba_transfer:
        return jsonify({"shadow_pokemon": []})
    game = request.args.get("game", "colosseum")
    if game == "xd_gale":
        shadow_list = gba_transfer.get_xd_shadow_list()
    else:
        shadow_list = gba_transfer.get_colosseum_shadow_list()
    return jsonify({"shadow_pokemon": shadow_list})

@app.route("/api/gba/version-exclusives")
def api_gba_version_exclusives():
    """Get version-exclusive Pokemon for a GBA game."""
    if not gba_transfer:
        return jsonify({"exclusives": []})
    game_str = request.args.get("game", "ruby")
    try:
        game = GBAGame(game_str)
        info = gba_transfer.get_version_exclusives_info(game)
        return jsonify(info)
    except ValueError:
        return jsonify({"error": f"Unknown game: {game_str}"}), 400

# Memory Card Routes

@app.route("/memory-card")
def memory_card():
    """Memory Card manager page."""
    saved_cards = memory_card_manager.list_saved_cards() if memory_card_manager else []
    return render_template("memory_card.html", saved_cards=saved_cards)

@app.route("/api/memory-card/import-gci", methods=["POST"])
def api_mc_import_gci():
    """Import a .gci file."""
    if not memory_card_manager:
        return jsonify({"success": False, "error": "Memory card module unavailable"}), 503
    if "gci_file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    f = request.files["gci_file"]
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".gci", delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name
    try:
        card = memory_card_manager.load_gci(tmp_path)
        if card is None:
            return jsonify({"success": False, "error": "Failed to parse GCI file"}), 400
        return jsonify({"success": True, "card": card.to_dict()})
    finally:
        os.unlink(tmp_path)

@app.route("/api/memory-card/create", methods=["POST"])
def api_mc_create():
    """Create a new virtual Memory Card."""
    if not memory_card_manager:
        return jsonify({"success": False, "error": "Memory card module unavailable"}), 503
    data = request.get_json() or {}
    label = data.get("label", "Memory Card A")[:32]
    size_mb = int(data.get("size_mb", 59))
    card = memory_card_manager.create_new_card(label=label, size_mb=size_mb)
    saved_path = memory_card_manager.save_ptbmc(card)
    return jsonify({"success": True, "card": card.to_dict(), "file_path": saved_path})

@app.route("/api/memory-card/load", methods=["POST"])
def api_mc_load():
    """Load a .ptbmc file."""
    if not memory_card_manager:
        return jsonify({"success": False, "error": "Memory card module unavailable"}), 503
    data = request.get_json() or {}
    file_path = data.get("file_path", "")
    card = memory_card_manager.load_ptbmc(file_path)
    if card is None:
        return jsonify({"success": False, "error": "Failed to load card"}), 400
    return jsonify({"success": True, "card": card.to_dict()})

@app.route("/api/memory-card/save", methods=["POST"])
def api_mc_save():
    """Save a MemoryCard to .ptbmc."""
    if not memory_card_manager:
        return jsonify({"success": False, "error": "Memory card module unavailable"}), 503
    data = request.get_json() or {}
    try:
        from src.features.memory_card import MemoryCard as MC
        card = MC.from_dict(data.get("card", {}))
        saved_path = memory_card_manager.save_ptbmc(card)
        return jsonify({"success": True, "file_path": saved_path})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/memory-card/delete", methods=["POST"])
def api_mc_delete():
    """Delete a .ptbmc file."""
    if not memory_card_manager:
        return jsonify({"success": False, "error": "Memory card module unavailable"}), 503
    data = request.get_json() or {}
    file_path = data.get("file_path", "")
    ok = memory_card_manager.delete_card(file_path)
    return jsonify({"success": ok, "error": None if ok else "File not found or not a .ptbmc"})

@app.route("/api/memory-card/list")
def api_mc_list():
    """List all saved .ptbmc files."""
    if not memory_card_manager:
        return jsonify({"cards": []})
    return jsonify({"cards": memory_card_manager.list_saved_cards()})

# API Routes

@app.route('/api/pokemon/search')
def api_pokemon_search():
    """Search Pokemon API."""
    query = request.args.get('q', '').lower()
    
    # Mock Pokemon data - in real app, this would query the database
    pokemon_list = [
        {'id': 1, 'name': 'Bulbasaur', 'types': ['Grass', 'Poison']},
        {'id': 4, 'name': 'Charmander', 'types': ['Fire']},
        {'id': 7, 'name': 'Squirtle', 'types': ['Water']},
        {'id': 25, 'name': 'Pikachu', 'types': ['Electric']},
        {'id': 150, 'name': 'Mewtwo', 'types': ['Psychic']},
        {'id': 249, 'name': 'Lugia', 'types': ['Psychic', 'Flying']},
    ]
    
    if query:
        pokemon_list = [p for p in pokemon_list if query in p['name'].lower()]
    
    return jsonify(pokemon_list)

@app.route('/api/teams', methods=['GET', 'POST'])
@require_login
def api_teams():
    """Teams API."""
    user = get_current_user()
    
    if request.method == 'POST':
        # Create new team
        data = request.get_json()
        
        team_name = data.get('name', '').strip()
        if not team_name:
            return jsonify({'error': 'Team name is required'}), 400
        
        # Create team
        team_id = f"team_{len(teams_db) + 1}"
        team_data = {
            'id': team_id,
            'name': team_name,
            'owner_id': user.id,
            'pokemon': data.get('pokemon', []),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        teams_db[team_id] = team_data
        user.teams.append(team_id)
        
        return jsonify({'success': True, 'team': team_data})
    
    else:
        # Get user's teams
        user_teams = [teams_db[team_id] for team_id in user.teams if team_id in teams_db]
        return jsonify(user_teams)

@app.route('/api/teams/<team_id>', methods=['GET', 'PUT', 'DELETE'])
@require_login
def api_team_detail(team_id):
    """Individual team API."""
    user = get_current_user()
    
    if team_id not in teams_db:
        return jsonify({'error': 'Team not found'}), 404
    
    team = teams_db[team_id]
    
    # Check ownership
    if team['owner_id'] != user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    if request.method == 'GET':
        return jsonify(team)
    
    elif request.method == 'PUT':
        # Update team
        data = request.get_json()
        
        if 'name' in data:
            team['name'] = data['name']
        if 'pokemon' in data:
            team['pokemon'] = data['pokemon']
        
        team['updated_at'] = datetime.now().isoformat()
        
        return jsonify({'success': True, 'team': team})
    
    elif request.method == 'DELETE':
        # Delete team
        del teams_db[team_id]
        user.teams.remove(team_id)
        
        return jsonify({'success': True})

@app.route('/api/teams/<team_id>/analyze')
@require_login
def api_analyze_team(team_id):
    """Analyze team API."""
    user = get_current_user()
    
    if team_id not in teams_db:
        return jsonify({'error': 'Team not found'}), 404
    
    team_data = teams_db[team_id]
    
    if team_data['owner_id'] != user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Convert to PokemonTeam object for analysis
    try:
        team = PokemonTeam(name=team_data['name'])
        
        for pokemon_data in team_data['pokemon']:
            # Create Pokemon object (simplified)
            pokemon = Pokemon(
                name=pokemon_data.get('name', 'Unknown'),
                types=[PokemonType.NORMAL],  # Would be loaded from data
                stats=pokemon_data.get('stats', {})
            )
            team.add_pokemon(pokemon)
        
        # Analyze team
        analysis = team_analyzer.analyze_team(team)
        
        return jsonify({
            'success': True,
            'analysis': {
                'type_coverage': analysis.get('type_coverage', {}),
                'weaknesses': analysis.get('weaknesses', []),
                'strengths': analysis.get('strengths', []),
                'suggestions': analysis.get('suggestions', [])
            }
        })
        
    except Exception as e:
        logger.error(f"Team analysis error: {e}")
        return jsonify({'error': 'Analysis failed'}), 500

@app.route('/api/breeding/calculate', methods=['POST'])
@require_login
def api_breeding_calculate():
    """Breeding calculation API."""
    data = request.get_json()
    
    parent1_data = data.get('parent1', {})
    parent2_data = data.get('parent2', {})
    
    try:
        # Simplified breeding calculation
        result = {
            'success': True,
            'offspring': {
                'species': parent1_data.get('species', 'Unknown'),
                'possible_natures': ['Hardy', 'Lonely', 'Brave', 'Adamant', 'Naughty'],
                'iv_ranges': {
                    'hp': [15, 31],
                    'attack': [15, 31],
                    'defense': [15, 31],
                    'sp_attack': [15, 31],
                    'sp_defense': [15, 31],
                    'speed': [15, 31]
                },
                'inheritance_chance': 0.85,
                'estimated_stats': {
                    'hp': 100,
                    'attack': 80,
                    'defense': 75,
                    'sp_attack': 90,
                    'sp_defense': 85,
                    'speed': 95
                }
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Breeding calculation error: {e}")
        return jsonify({'error': 'Calculation failed'}), 500

@app.route('/api/tournaments', methods=['GET', 'POST'])
def api_tournaments():
    """Tournaments API."""
    if request.method == 'POST':
        # Create tournament (requires login)
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        name = data.get('name', '').strip()
        format_type = data.get('format', 'single_elimination')
        max_players = data.get('max_players', 16)
        
        if not name:
            return jsonify({'error': 'Tournament name is required'}), 400
        
        try:
            tournament_format = TournamentFormat(format_type)
            tournament = tournament_manager.create_tournament(name, tournament_format, max_players)
            
            return jsonify({
                'success': True,
                'tournament': tournament.export_results()
            })
            
        except Exception as e:
            logger.error(f"Tournament creation error: {e}")
            return jsonify({'error': 'Failed to create tournament'}), 500
    
    else:
        # Get tournaments
        active_tournaments = tournament_manager.get_active_tournaments()
        tournaments_data = [t.export_results() for t in active_tournaments]
        
        return jsonify(tournaments_data)

@app.route('/api/tournaments/<tournament_id>/join', methods=['POST'])
@require_login
def api_join_tournament(tournament_id):
    """Join tournament API."""
    user = get_current_user()
    
    tournament = tournament_manager.get_tournament(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    data = request.get_json()
    team_id = data.get('team_id')
    
    if team_id and team_id in teams_db:
        team_data = teams_db[team_id]
        if team_data['owner_id'] != user.id:
            return jsonify({'error': 'Team access denied'}), 403
    
    # Register player
    success = tournament_manager.register_player(tournament_id, user.username)
    
    if success:
        return jsonify({'success': True, 'message': 'Joined tournament successfully'})
    else:
        return jsonify({'error': 'Failed to join tournament'}), 400

# WebSocket Events for Real-time Features

@socketio.on('connect')
def on_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to Pokemon Team Builder'})

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('join_room')
def on_join_room(data):
    """Join a room for real-time updates."""
    room = data.get('room')
    if room:
        join_room(room)
        emit('joined_room', {'room': room})
        logger.info(f"Client {request.sid} joined room {room}")

@socketio.on('leave_room')
def on_leave_room(data):
    """Leave a room."""
    room = data.get('room')
    if room:
        leave_room(room)
        emit('left_room', {'room': room})
        logger.info(f"Client {request.sid} left room {room}")

@socketio.on('battle_move')
def on_battle_move(data):
    """Handle battle move in real-time."""
    battle_id = data.get('battle_id')
    move = data.get('move')
    
    if battle_id and move:
        # Process battle move
        # This would integrate with the battle engine
        
        # Broadcast move to battle room
        emit('battle_update', {
            'battle_id': battle_id,
            'move': move,
            'timestamp': datetime.now().isoformat()
        }, room=f"battle_{battle_id}")

@socketio.on('tournament_update')
def on_tournament_update(data):
    """Handle tournament updates."""
    tournament_id = data.get('tournament_id')
    
    if tournament_id:
        tournament = tournament_manager.get_tournament(tournament_id)
        if tournament:
            # Broadcast tournament update
            emit('tournament_updated', {
                'tournament_id': tournament_id,
                'data': tournament.get_bracket_data()
            }, room=f"tournament_{tournament_id}")

# Error Handlers

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('500.html'), 500

# Context Processors

@app.context_processor
def inject_user():
    """Inject current user into templates."""
    return {'current_user': get_current_user()}

@app.context_processor
def inject_datetime():
    """Inject datetime into templates."""
    return {'datetime': datetime}

# Development configuration
# ── Health Check & Utility Routes ────────────────────────────────────────────

@app.route("/health")
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return jsonify({
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": {
            "memory_card": memory_card_manager is not None,
            "gba_support":  gba_parser is not None,
            "tournaments":  True,
        }
    })

@app.route("/robots.txt")
def robots_txt():
    """Robots.txt for search engine crawlers."""
    from flask import Response
    return Response("User-agent: *\nDisallow: /api/\nDisallow: /admin/\n",
                    mimetype="text/plain")

if __name__ == '__main__':
    # Create templates and static directories if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    
    # Run the application
    logger.info("Starting Pokemon Team Builder Web Application")
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "False").lower() == "true"
    logger.info(f"Starting PTB on {host}:{port} (debug={debug})")
    socketio.run(app, debug=debug, host=host, port=port)
