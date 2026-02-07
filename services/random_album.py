# File: metalwall_app/services/random_album.py
# ===========================
# RANDOM ALBUM DISCOVERY SERVICE
# ===========================

import streamlit as st
import random
import time
import difflib
import re
from typing import Optional, Dict, Tuple, List
from database.operations import load_albums, save_discovery
from services.spotify_service import get_spotify_client, get_related_artists_spotify, get_random_album_by_artist
from services.lastfm_service import get_lastfm_client, get_related_artists_lastfm
from services.bandcamp_service import bandcamp_search

# Strict metal validation keywords
METAL_KEYWORDS = ['metal', 'grind', 'metalcore', 'heavy', 'death', 'black', 'thrash', 
                  'doom', 'power', 'sludge', 'stoner', 'progressive metal', 'deathcore']

# Problematic band name mappings (common misidentifications)
PROBLEMATIC_BAND_MAPPINGS = {
    'sabbat': ['black sabbath'],  # Sabbat is a different band than Black Sabbath
    'incantation': ['blood incantation'],  # Different bands
    'cattle decapitation': ['decapitated'],  # Different bands
    'sodom': ['sodomized'],  # Sodom vs Sodomized
    'mayhem': ['mayhems'],  # Mayhem vs Mayhems
    'cannibal corpse': ['cannibal'],  # Cannibal Corpse vs Cannibal
    'darkthrone': ['dark throne', 'darkthrones'],  # Common misspellings
    'immortal': ['immortals'],  # Immortal vs Immortals
    'morbid angel': ['morbid', 'angel'],  # Morbid Angel vs separate words
}

def normalize_band_name(name: str) -> str:
    """Normalize band name for comparison"""
    if not name:
        return ""
    
    # Convert to lowercase
    name = name.lower()
    
    # Remove common prefixes/suffixes and special characters
    name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation
    name = re.sub(r'\b(the|a|an|and|or|but)\b', '', name)  # Remove common words
    name = re.sub(r'\s+', ' ', name).strip()  # Normalize whitespace
    
    return name

def are_bands_similar(band1: str, band2: str, threshold: float = 0.7) -> bool:
    """Check if two band names are similar enough to be confused"""
    band1_norm = normalize_band_name(band1)
    band2_norm = normalize_band_name(band2)
    
    # Check for problematic mappings
    for base_band, confusions in PROBLEMATIC_BAND_MAPPINGS.items():
        base_norm = normalize_band_name(base_band)
        if base_norm == band1_norm:
            for confusion in confusions:
                confusion_norm = normalize_band_name(confusion)
                if confusion_norm == band2_norm:
                    return True
        elif base_norm == band2_norm:
            for confusion in confusions:
                confusion_norm = normalize_band_name(confusion)
                if confusion_norm == band1_norm:
                    return True
    
    # Use sequence matching as fallback
    similarity = difflib.SequenceMatcher(None, band1_norm, band2_norm).ratio()
    return similarity > threshold

def get_random_album_from_wall() -> Optional[Dict]:
    """Get a random album from the wall"""
    try:
        albums = load_albums()
        if albums:
            album = random.choice(albums)
            return {
                'id': album.id,
                'username': album.username,
                'url': album.url,
                'artist': album.artist,
                'album_name': album.album_name,
                'cover_url': album.cover_url,
                'platform': album.platform,
                'tags': album.tags,
                'likes': album.likes,
                'timestamp': album.timestamp
            }
        return None
    except Exception as e:
        st.error(f"Error getting random album: {e}")
        return None

def is_metal_artist(lastfm_client, artist_name: str) -> Tuple[bool, List[str], str]:
    """
    Strict check if an artist is a metal artist using Last.fm tags
    Returns: (is_metal, list_of_tags, original_artist_name)
    """
    if not lastfm_client:
        return False, [], artist_name
    
    try:
        # Get artist info from Last.fm
        artist = lastfm_client.get_artist(artist_name)
        original_name = artist.get_name()  # Get the canonical name from Last.fm
        
        # Get top tags for the artist
        tags = artist.get_top_tags(limit=15)
        
        # Convert tags to lowercase for comparison
        tag_names = [tag.item.get_name().lower() for tag in tags]
        
        # STRICT metal validation - check for specific metal keywords
        metal_tags_found = []
        for tag in tag_names:
            for keyword in METAL_KEYWORDS:
                if keyword in tag:
                    metal_tags_found.append(tag)
        
        # Require at least one strong metal tag
        if metal_tags_found:
            return True, tag_names, original_name
        
        return False, tag_names, original_name
        
    except Exception as e:
        print(f"Error checking if {artist_name} is metal: {e}")
        return False, [], artist_name

def search_lastfm_artist_exact(lastfm_client, artist_name: str, album_name: str = None) -> Optional[Dict]:
    """
    Search for an artist on Last.fm with exact matching
    Returns: dict with artist info if found
    """
    if not lastfm_client:
        return None
    
    try:
        # Try to get the artist directly first
        try:
            artist = lastfm_client.get_artist(artist_name)
            artist_name_corrected = artist.get_name()
            
            # Get artist tags
            tags = artist.get_top_tags(limit=15)
            tag_names = [tag.item.get_name().lower() for tag in tags]
            
            # Get top albums to verify
            top_albums = []
            if album_name:
                albums = artist.get_top_albums(limit=10)
                top_albums = [album.item.get_name().lower() for album in albums]
            
            return {
                'artist': artist_name_corrected,
                'tags': tag_names,
                'top_albums': top_albums,
                'mbid': artist.get_mbid() if hasattr(artist, 'get_mbid') else None
            }
        except Exception:
            pass
        
        # If direct get fails, try search
        search_results = lastfm_client.search_for_artist(artist_name)
        
        if search_results and len(search_results) > 0:
            # Get all results and find the best match
            for result in search_results:
                result_name = result.get_name()
                
                # Check for exact or very close match
                if normalize_band_name(result_name) == normalize_band_name(artist_name):
                    artist = lastfm_client.get_artist(result_name)
                    tags = artist.get_top_tags(limit=15)
                    tag_names = [tag.item.get_name().lower() for tag in tags]
                    
                    return {
                        'artist': result_name,
                        'tags': tag_names,
                        'top_albums': [],
                        'mbid': artist.get_mbid() if hasattr(artist, 'get_mbid') else None
                    }
    
    except Exception as e:
        print(f"Error searching Last.fm for artist {artist_name}: {e}")
    
    return None

def validate_and_correct_metal_album(lastfm_client, spotify_album_data: Dict, original_artist: str = None) -> Tuple[Optional[Dict], bool, str]:
    """
    STRICT validation if an album is metal with double checking
    Returns: (corrected_album_data, is_valid, validation_message)
    """
    if not lastfm_client:
        return spotify_album_data, True, "Warning: No Last.fm validation available"
    
    spotify_artist = spotify_album_data.get('artist', '')
    album_name = spotify_album_data.get('album', '')
    
    # Step 1: Get EXACT artist info from Last.fm
    lastfm_artist_info = search_lastfm_artist_exact(lastfm_client, spotify_artist)
    
    if not lastfm_artist_info:
        return None, False, f"Artist '{spotify_artist}' not found on Last.fm"
    
    lastfm_artist_name = lastfm_artist_info['artist']
    lastfm_tags = lastfm_artist_info['tags']
    
    # Step 2: Check for problematic band confusion
    if are_bands_similar(lastfm_artist_name, original_artist or spotify_artist):
        # This might be a confusingly similar but different band
        return None, False, f"Potential band confusion: '{lastfm_artist_name}' vs '{original_artist or spotify_artist}'"
    
    # Step 3: Check if the Last.fm artist name matches Spotify artist name
    normalized_lastfm = normalize_band_name(lastfm_artist_name)
    normalized_spotify = normalize_band_name(spotify_artist)
    
    if normalized_lastfm != normalized_spotify:
        # They don't match - this could be a different band
        # Check if it's a close match but might be acceptable
        similarity = difflib.SequenceMatcher(None, normalized_lastfm, normalized_spotify).ratio()
        if similarity < 0.9:
            return None, False, f"Artist name mismatch: Last.fm='{lastfm_artist_name}', Spotify='{spotify_artist}'"
    
    # Step 4: Check for metal tags
    metal_tags_found = []
    for tag in lastfm_tags:
        for keyword in METAL_KEYWORDS:
            if keyword in tag:
                metal_tags_found.append(tag)
    
    if not metal_tags_found:
        # Check if the artist is metal using the more comprehensive check
        is_metal, all_tags, canonical_name = is_metal_artist(lastfm_client, lastfm_artist_name)
        if not is_metal:
            return None, False, "No metal tags found on Last.fm"
        
        # Update with canonical name if different
        if canonical_name != spotify_artist:
            spotify_album_data['artist'] = canonical_name
    
    # Step 5: Update album data with Last.fm info
    spotify_album_data['lastfm_tags'] = lastfm_tags
    spotify_album_data['metal_tags'] = metal_tags_found
    spotify_album_data['lastfm_artist_name'] = lastfm_artist_name
    
    # Count metal tags for validation message
    metal_tag_count = len(metal_tags_found)
    
    return spotify_album_data, True, f"✅ Validated: {metal_tag_count} metal tags found"

def get_metal_related_artists(lastfm_client, base_artist: str, max_results: int = 10) -> List[str]:
    """
    Get related artists and filter to only metal ones
    """
    if not lastfm_client:
        return []
    
    try:
        # Get all related artists
        artist = lastfm_client.get_artist(base_artist)
        similar = artist.get_similar(limit=20)
        
        # Filter to only metal artists
        metal_related = []
        for similar_artist in similar:
            artist_name = similar_artist.item.get_name()
            
            # Skip if it's a problematic similar band
            if are_bands_similar(artist_name, base_artist):
                continue
            
            is_metal, tags, _ = is_metal_artist(lastfm_client, artist_name)
            
            if is_metal:
                metal_related.append(artist_name)
                
                if len(metal_related) >= max_results:
                    break
        
        return metal_related
        
    except Exception as e:
        print(f"Error getting metal related artists: {e}")
        return []

def get_spotify_artist_exact(spotify_client, artist_name: str) -> Optional[Dict]:
    """
    Get exact artist match from Spotify with verification
    """
    if not spotify_client:
        return None
    
    try:
        # Search for artist
        results = spotify_client.search(q=f'artist:{artist_name}', type='artist', limit=10)
        
        if not results or 'artists' not in results or not results['artists']['items']:
            return None
        
        # Find the best match
        for artist in results['artists']['items']:
            spotify_artist_name = artist.get('name', '')
            
            # Check for exact or normalized match
            if (normalize_band_name(spotify_artist_name) == normalize_band_name(artist_name) or
                spotify_artist_name.lower() == artist_name.lower()):
                return {
                    'id': artist.get('id'),
                    'name': spotify_artist_name,
                    'genres': artist.get('genres', []),
                    'popularity': artist.get('popularity'),
                    'uri': artist.get('uri')
                }
        
        # If no exact match, try with higher similarity
        for artist in results['artists']['items']:
            spotify_artist_name = artist.get('name', '')
            similarity = difflib.SequenceMatcher(None, 
                                                normalize_band_name(spotify_artist_name),
                                                normalize_band_name(artist_name)).ratio()
            
            if similarity > 0.9:  # Very high similarity required
                return {
                    'id': artist.get('id'),
                    'name': spotify_artist_name,
                    'genres': artist.get('genres', []),
                    'popularity': artist.get('popularity'),
                    'uri': artist.get('uri')
                }
    
    except Exception as e:
        print(f"Error getting exact artist from Spotify: {e}")
    
    return None

def discover_random_album(base_artist: Optional[str] = None, base_album_obj: Optional[Dict] = None, 
                         max_attempts: int = 15) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Main random discovery function with STRICT metal validation and exact matching
    """
    try:
        # Get Spotify and Last.fm clients
        spotify_client = get_spotify_client()
        lastfm_client = get_lastfm_client()
        
        # Step 1: Get random album from wall (or use provided)
        if base_album_obj is None:
            random_album = get_random_album_from_wall()
            if not random_album:
                return None, "No albums found in the wall"
        else:
            random_album = base_album_obj
        
        base_artist_name = random_album.get('artist', '')
        base_album_name = random_album.get('album_name', '')
        
        # Clean artist name
        from services.spotify_service import clean_artist_name
        base_artist_name_clean = clean_artist_name(base_artist_name)
        
        if not base_artist_name_clean:
            return None, "Could not extract artist from album"
        
        # Step 2: Verify base artist is metal
        if lastfm_client:
            is_base_metal, base_tags, base_canonical = is_metal_artist(lastfm_client, base_artist_name_clean)
            if not is_base_metal:
                st.warning(f"Warning: Base artist '{base_artist_name_clean}' may not be metal. Found tags: {', '.join(base_tags[:5])}")
        
        # Step 3: Find metal-related artists only
        metal_related_artists = []
        
        # Try to get metal-only related artists from Last.fm
        if lastfm_client:
            metal_related_artists = get_metal_related_artists(lastfm_client, base_artist_name_clean)
        
        # Fallback to Spotify if no metal artists found
        if not metal_related_artists and spotify_client:
            all_related = get_related_artists_spotify(spotify_client, base_artist_name_clean)
            # Filter Spotify results through Last.fm validation
            for artist in all_related[:10]:
                if lastfm_client:
                    is_metal, _, _ = is_metal_artist(lastfm_client, artist)
                    if is_metal:
                        metal_related_artists.append(artist)
        
        if not metal_related_artists:
            return None, f"No metal-related artists found for {base_artist_name_clean}"
        
        # Try multiple attempts to find a valid metal album
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            
            # Step 4: Pick random metal-related artist
            random_metal_artist = random.choice(metal_related_artists)
            
            # Step 5: Get EXACT artist match from Spotify first
            spotify_artist_info = None
            if spotify_client:
                spotify_artist_info = get_spotify_artist_exact(spotify_client, random_metal_artist)
            
            # If we can't find the exact artist on Spotify, skip
            if not spotify_artist_info:
                continue
            
            # Step 6: Get random album from the EXACT Spotify artist
            random_album_data = None
            if spotify_client:
                # Use the artist ID to get albums (more reliable than name search)
                try:
                    artist_id = spotify_artist_info['id']
                    # Get artist's albums
                    albums = spotify_client.artist_albums(artist_id, limit=20)
                    
                    if albums and albums.get('items'):
                        # Pick a random album
                        album = random.choice(albums['items'])
                        
                        random_album_data = {
                            "artist": spotify_artist_info['name'],
                            "album": album.get('name', 'Unknown Album'),
                            "image": album.get('images', [{}])[0].get('url') if album.get('images') else None,
                            "url": album.get('external_urls', {}).get('spotify', ''),
                            "release_date": album.get('release_date', 'Unknown'),
                            "total_tracks": album.get('total_tracks', 0),
                            "genres": spotify_artist_info['genres'],
                            "spotify_artist_id": artist_id
                        }
                except Exception as e:
                    print(f"Error getting albums for artist {random_metal_artist}: {e}")
            
            # If Spotify fails, skip this attempt
            if not random_album_data:
                continue
            
            # Step 7: STRICT validation with double checking
            if lastfm_client:
                validated_album, is_valid, validation_msg = validate_and_correct_metal_album(
                    lastfm_client, random_album_data, random_metal_artist
                )
                
                if is_valid and validated_album:
                    # FINAL VERIFICATION: Check that the validated artist matches our searched artist
                    validated_artist = validated_album.get("artist", "")
                    
                    # Skip if it's a problematic confusion
                    if are_bands_similar(validated_artist, random_metal_artist):
                        continue
                    
                    # Check normalization
                    if normalize_band_name(validated_artist) != normalize_band_name(random_metal_artist):
                        similarity = difflib.SequenceMatcher(None, 
                                                            normalize_band_name(validated_artist),
                                                            normalize_band_name(random_metal_artist)).ratio()
                        if similarity < 0.95:  # Very strict threshold
                            continue
                    
                    # Step 8: Try to find the album on Bandcamp
                    bandcamp_result = None
                    try:
                        bc_search_result = bandcamp_search(
                            validated_album["artist"], 
                            validated_album["album"]
                        )
                        if bc_search_result:
                            bandcamp_result = {
                                "url": bc_search_result["url"],
                                "artist": bc_search_result["artist"],
                                "album": bc_search_result["album"]
                            }
                    except Exception:
                        pass
                    
                    # Prepare discovery data
                    discovery_data = {
                        "origin": {
                            "album": random_album,
                            "artist": base_artist_name,
                            "album_name": base_album_name
                        },
                        "discovery": {
                            **validated_album,
                            "searched_artist": random_metal_artist,
                            "validation_details": validation_msg
                        },
                        "bandcamp": bandcamp_result,
                        "description": f"Based on '{base_album_name}' by {base_artist_name} → Metal-related artist: {random_metal_artist}",
                        "validation": validation_msg,
                        "exact_match": "✅ Exact artist match" if validated_artist == random_metal_artist else "⚠️ Corrected artist"
                    }
                    
                    # Save discovery to database
                    if st.session_state.get('current_user'):
                        save_discovery(
                            username=st.session_state.current_user,
                            base_artist=base_artist_name,
                            base_album=base_album_name,
                            discovered_artist=validated_album["artist"],
                            discovered_album=validated_album["album"],
                            discovered_url=validated_album["url"],
                            cover_url=validated_album.get("image")
                        )
                    
                    return discovery_data, None
                else:
                    # Not a valid metal album, try again
                    continue
            else:
                # No Last.fm client, create basic discovery with warning
                bandcamp_result = None
                try:
                    if random_album_data:
                        bc_search_result = bandcamp_search(random_metal_artist, random_album_data["album"])
                        if bc_search_result:
                            bandcamp_result = {
                                "url": bc_search_result["url"],
                                "artist": bc_search_result["artist"],
                                "album": bc_search_result["album"]
                            }
                except Exception:
                    pass
                
                discovery_data = {
                    "origin": {
                        "album": random_album,
                        "artist": base_artist_name,
                        "album_name": base_album_name
                    },
                    "discovery": random_album_data,
                    "bandcamp": bandcamp_result,
                    "description": f"Based on '{base_album_name}' by {base_artist_name} → Related artist: {random_metal_artist}",
                    "validation": "⚠️ No Last.fm validation available",
                }
                
                return discovery_data, None
        
        return None, f"Could not find a validated metal album after {max_attempts} attempts. Try again!"
        
    except Exception as e:
        return None, f"Error during discovery: {str(e)}"