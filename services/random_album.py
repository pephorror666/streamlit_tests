# File: metalwall_app/services/random_album.py
# ===========================
# RANDOM ALBUM DISCOVERY SERVICE
# ===========================

import streamlit as st
import random
import time
import re
import urllib.parse
from typing import Optional, Dict, Tuple, List
from fuzzywuzzy import fuzz
from database.operations import load_albums, save_discovery
from services.spotify_service import get_spotify_client, get_related_artists_spotify, get_random_album_by_artist
from services.lastfm_service import get_lastfm_client, get_related_artists_lastfm
from services.bandcamp_service import bandcamp_search

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

# Add this function to your random_album.py file:

# Add this to your random_album.py file:

def prepare_discovery_for_posting(discovery_data: Dict) -> Dict:
    """
    Prepare discovery data for posting to wall
    Ensures we have a valid URL and all required fields
    """
    try:
        discovery = discovery_data.get('discovery', {})
        bandcamp = discovery_data.get('bandcamp')
        
        # Priority 1: Use Bandcamp URL if available
        if bandcamp and bandcamp.get('url'):
            return {
                'url': bandcamp['url'],
                'artist': bandcamp.get('artist') or discovery.get('artist', ''),
                'album': bandcamp.get('album') or discovery.get('album', ''),
                'image_url': discovery.get('image')
            }
        
        # Priority 2: Use Spotify URL
        spotify_url = discovery.get('url', '')
        if spotify_url and 'open.spotify.com' in spotify_url:
            return {
                'url': spotify_url,
                'artist': discovery.get('artist', ''),
                'album': discovery.get('album', ''),
                'image_url': discovery.get('image')
            }
        
        # Priority 3: Use Last.fm URL
        artist_name = discovery.get('artist', '')
        if artist_name:
            # Create a Last.fm search URL
            lastfm_url = f"https://www.last.fm/music/{urllib.parse.quote(artist_name.replace(' ', '+'))}"
            return {
                'url': lastfm_url,
                'artist': artist_name,
                'album': discovery.get('album', ''),
                'image_url': discovery.get('image')
            }
        
        # Fallback: Use whatever we have
        return {
            'url': discovery.get('url', ''),
            'artist': discovery.get('artist', ''),
            'album': discovery.get('album', ''),
            'image_url': discovery.get('image')
        }
        
    except Exception as e:
        print(f"Error preparing discovery for posting: {e}")
        return {}

def normalize_artist_name(artist_name: str) -> str:
    """
    Normalize artist name for better matching:
    - Remove common prefixes/suffixes
    - Standardize special characters
    - Remove extra whitespace
    """
    if not artist_name:
        return ""
    
    # Convert to lowercase
    name = artist_name.lower()
    
    # Remove common prefixes/suffixes
    prefixes_to_remove = ['the ', '"', "'"]
    for prefix in prefixes_to_remove:
        if name.startswith(prefix):
            name = name[len(prefix):]
    
    # Standardize special characters
    name = re.sub(r'[&\+]', ' and ', name)
    name = re.sub(r'[^a-z0-9\s]', '', name)
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    return name.strip()

def are_artists_similar(artist1: str, artist2: str, threshold: int = 85) -> bool:
    """
    Check if two artist names are similar using fuzzy matching.
    Helps avoid confusion like 'Cattle Decapitation' vs 'Decapitation'
    """
    norm1 = normalize_artist_name(artist1)
    norm2 = normalize_artist_name(artist2)
    
    # Quick exact match check
    if norm1 == norm2:
        return True
    
    # Check if one is contained in the other (partial match)
    if norm1 in norm2 or norm2 in norm1:
        # But make sure it's not just a single word match
        words1 = norm1.split()
        words2 = norm2.split()
        
        # If both are single words, partial match is OK
        if len(words1) == 1 and len(words2) == 1:
            return norm1 in norm2 or norm2 in norm1
        
        # If one is multi-word and other is single word, be careful
        if len(words1) == 1 or len(words2) == 1:
            # Check if the single word is actually a full band name match
            # or just a partial match (like "Decapitation" vs "Cattle Decapitation")
            single_word = words1[0] if len(words1) == 1 else words2[0]
            multi_words = words2 if len(words1) == 1 else words1
            
            # Check if single word appears in multi-word name
            if single_word in multi_words:
                # This is likely a partial match (bad)
                return False
    
    # Use fuzzy matching for similarity
    similarity = fuzz.ratio(norm1, norm2)
    
    # Also check token set ratio (order-independent)
    token_similarity = fuzz.token_set_ratio(artist1.lower(), artist2.lower())
    
    return similarity >= threshold or token_similarity >= threshold

def is_metal_artist(lastfm_client, artist_name: str) -> bool:
    """
    Check if an artist is a metal artist using Last.fm tags
    Returns True if artist has metal-related tags
    """
    if not lastfm_client:
        return False
    
    try:
        # Get artist info from Last.fm
        artist = lastfm_client.get_artist(artist_name)
        
        # Get top tags for the artist
        tags = artist.get_top_tags(limit=15)
        
        # Convert tags to lowercase for comparison
        tag_names = [tag.item.get_name().lower() for tag in tags]
        
        # Extended metal-related keywords with weights
        metal_keywords = {
            # Strong metal indicators
            'metal': 2.0,
            'heavy metal': 2.0,
            'death metal': 2.0,
            'black metal': 2.0,
            'thrash metal': 2.0,
            'power metal': 2.0,
            'folk metal': 2.0,
            'symphonic metal': 2.0,
            'doom metal': 2.0,
            'progressive metal': 2.0,
            'melodic death metal': 2.0,
            'grindcore': 2.0,
            'goregrind': 2.0,
            'deathcore': 2.0,
            'metalcore': 2.0,
            'hardcore': 1.5,
            'post-metal': 2.0,
            'avant-garde metal': 2.0,
            'sludge metal': 2.0,
            'stoner metal': 2.0,
            'nu metal': 2.0,
            'industrial metal': 2.0,
            'gothic metal': 2.0,
            'speed metal': 2.0,
            'glam metal': 1.8,
            'hair metal': 1.8,
            'neoclassical metal': 2.0,
            'djent': 2.0,
            'math metal': 2.0,
            'alternative metal': 2.0,
            'viking metal': 2.0,
            'pagan metal': 2.0,
            'war metal': 2.0,
            'brutal death metal': 2.0,
            'technical death metal': 2.0,
            'crust': 1.8,
            'hardcore punk': 1.5,
            'crossover thrash': 2.0,
            'grunge': 1.0,
            # General metal-related
            'extreme metal': 2.0,
            'underground metal': 1.8,
            'death': 1.5,
            'black': 1.5,
            'thrash': 1.5,
            'doom': 1.5,
            'power': 1.5,
        }
        
        # Calculate metal score
        metal_score = 0
        for tag in tag_names:
            for keyword, weight in metal_keywords.items():
                if keyword in tag or tag in keyword:
                    metal_score += weight
        
        # Also check for non-metal tags that would disqualify
        non_metal_tags = ['pop', 'hip hop', 'rap', 'r&b', 'country', 'jazz', 'blues', 
                         'classical', 'electronic', 'dance', 'indie', 'folk', 'acoustic',
                         'singer-songwriter', 'latin', 'reggae', 'soul', 'funk', 'disco']
        
        non_metal_score = 0
        for tag in tag_names:
            for non_metal in non_metal_tags:
                if non_metal in tag:
                    non_metal_score += 1
        
        # Determine if metal
        # Need at least moderate metal score and not too many non-metal tags
        return metal_score >= 1.5 and non_metal_score <= 2
        
    except Exception as e:
        print(f"Error checking if {artist_name} is metal: {e}")
        return False

def search_lastfm_artist(lastfm_client, album_name: str, artist_name: str) -> Optional[Dict]:
    """
    Search for an album on Last.fm and get the correct artist info
    Returns: dict with artist name and tags if found
    """
    if not lastfm_client:
        return None
    
    try:
        # Clean the artist name for better searching
        clean_artist = artist_name.split('(')[0].strip()
        
        # Search for the specific album by this artist
        search_results = lastfm_client.search_for_album(album_name, clean_artist)
        
        if not search_results or len(search_results) == 0:
            # Try searching just by artist to get their albums
            try:
                artist = lastfm_client.get_artist(clean_artist)
                albums = artist.get_top_albums(limit=20)
                
                # Look for matching album by name
                for album in albums:
                    album_obj = album.item
                    if fuzz.partial_ratio(album_name.lower(), album_obj.get_name().lower()) > 70:
                        # Found matching album
                        tags = artist.get_top_tags(limit=10)
                        tag_names = [tag.item.get_name().lower() for tag in tags]
                        
                        return {
                            'artist': artist.get_name(),
                            'tags': tag_names,
                            'album': album_obj.get_name()
                        }
            except Exception:
                pass
        
        # If we still have results, use the first one
        if search_results and len(search_results) > 0:
            album = search_results[0]
            artist = album.get_artist()
            artist_name_corrected = artist.get_name()
            
            # Check if the found artist is similar to our search
            if not are_artists_similar(artist_name_corrected, clean_artist, threshold=70):
                return None
            
            tags = artist.get_top_tags(limit=10)
            tag_names = [tag.item.get_name().lower() for tag in tags]
            
            return {
                'artist': artist_name_corrected,
                'tags': tag_names,
                'album': album.get_name()
            }
    
    except Exception as e:
        print(f"Error searching Last.fm for {artist_name} - {album_name}: {e}")
    
    return None

def validate_and_correct_metal_album(lastfm_client, spotify_album_data: Dict) -> Tuple[Optional[Dict], bool]:
    """
    Validate if an album is metal and correct artist info using Last.fm
    Returns: (corrected_album_data, is_valid)
    """
    if not lastfm_client:
        # If no Last.fm client, we can't validate, so accept it
        return spotify_album_data, True
    
    artist_name = spotify_album_data.get('artist', '')
    album_name = spotify_album_data.get('album', '')
    
    # Step 1: Check if the artist is already metal
    if is_metal_artist(lastfm_client, artist_name):
        return spotify_album_data, True
    
    # Step 2: Search for the album on Last.fm to get correct artist info
    lastfm_info = search_lastfm_artist(lastfm_client, album_name, artist_name)
    
    if lastfm_info:
        corrected_artist = lastfm_info['artist']
        tags = lastfm_info['tags']
        
        # Check if we got the right artist (not a partial match)
        if not are_artists_similar(corrected_artist, artist_name, threshold=70):
            return None, False
        
        # Check if the corrected artist is metal
        metal_keywords = ['metal', 'grindcore', 'death', 'thrash', 'crust', 'sludge', 
                         'heavy', 'black', 'doom', 'power', 'progressive', 'folk metal']
        
        metal_found = False
        for tag in tags:
            for keyword in metal_keywords:
                if keyword in tag:
                    metal_found = True
                    break
            if metal_found:
                break
        
        if metal_found:
            # Update the album data with corrected artist
            spotify_album_data['artist'] = corrected_artist
            return spotify_album_data, True
    
    # Step 3: Try alternative approach - search for similar artists to check if any are metal
    try:
        artist = lastfm_client.get_artist(artist_name)
        similar = artist.get_similar(limit=8)  # Get more similar artists
        
        metal_similar_count = 0
        for similar_artist in similar:
            similar_name = similar_artist.item.get_name()
            if is_metal_artist(lastfm_client, similar_name):
                metal_similar_count += 1
        
        # If most similar artists are metal, this is likely metal too
        if metal_similar_count >= 3:  # At least 3 out of 8 similar are metal
            return spotify_album_data, True
    
    except Exception:
        pass
    
    return None, False

def filter_related_artists(related_artists: List[str], base_artist: str) -> List[str]:
    """
    Filter out artists that are too similar or partial matches to avoid confusion
    """
    filtered = []
    base_normalized = normalize_artist_name(base_artist)
    
    for artist in related_artists:
        norm_artist = normalize_artist_name(artist)
        
        # Skip if too similar to base artist (might be same band with different name)
        if are_artists_similar(base_artist, artist, threshold=90):
            continue
        
        # Skip if artist name is contained in base artist name or vice versa
        # (e.g., skip "Decapitation" if base is "Cattle Decapitation")
        if base_normalized in norm_artist or norm_artist in base_normalized:
            # But allow if both are single words or if it's a legitimate partial
            words_base = base_normalized.split()
            words_artist = norm_artist.split()
            
            if len(words_base) > 1 and len(words_artist) == 1:
                # Single word artist from multi-word base - likely partial match
                continue
            if len(words_artist) > 1 and len(words_base) == 1:
                # Multi-word artist from single word base - check if it's a real partial
                if words_base[0] in words_artist:
                    continue
        
        filtered.append(artist)
    
    return filtered

def get_precise_spotify_album(spotify_client, artist_name: str) -> Optional[Dict]:
    """
    More precise Spotify album search that avoids wrong artist matches
    """
    if not spotify_client:
        return None
    
    try:
        # First, search for the artist to get their Spotify ID
        artist_results = spotify_client.search(q=f'artist:"{artist_name}"', type='artist', limit=5)
        
        if not artist_results or not artist_results['artists']['items']:
            return None
        
        # Find the best matching artist
        best_match = None
        best_score = 0
        
        for artist in artist_results['artists']['items']:
            spotify_artist_name = artist['name']
            similarity = fuzz.ratio(artist_name.lower(), spotify_artist_name.lower())
            
            # Extra penalty for partial matches
            if artist_name.lower() in spotify_artist_name.lower() or spotify_artist_name.lower() in artist_name.lower():
                if len(artist_name.split()) == 1 and len(spotify_artist_name.split()) > 1:
                    # Partial match (e.g., "Decapitation" vs "Cattle Decapitation")
                    similarity -= 30
            
            if similarity > best_score:
                best_score = similarity
                best_match = artist
        
        # Need a good match (at least 85% similarity)
        if best_score < 85:
            return None
        
        # Get the artist's albums
        artist_id = best_match['id']
        albums = spotify_client.artist_albums(artist_id, album_type='album,single', limit=50)
        
        if not albums['items']:
            return None
        
        # Filter out compilations and live albums
        valid_albums = []
        for album in albums['items']:
            album_type = album.get('album_type', '')
            album_name = album.get('name', '')
            
            # Skip compilations, live albums, and EPs (optional)
            if album_type == 'compilation':
                continue
            if 'live' in album_name.lower():
                continue
            if '(live' in album_name.lower():
                continue
            
            valid_albums.append(album)
        
        if not valid_albums:
            # If no valid albums, use the first one
            album = albums['items'][0]
        else:
            album = random.choice(valid_albums)
        
        # Get the largest available image
        images = album.get('images', [])
        image_url = images[0]['url'] if images else None
        
        return {
            "artist": best_match['name'],
            "album": album['name'],
            "image": image_url,
            "url": album['external_urls']['spotify'],
            "release_date": album.get('release_date', 'Unknown'),
            "total_tracks": album.get('total_tracks', 0),
            "genres": best_match.get('genres', [])
        }
        
    except Exception as e:
        print(f"Error getting precise Spotify album for {artist_name}: {e}")
        return None

def prepare_discovery_for_posting(discovery_data: Dict) -> Dict:
    """
    Prepare discovery data for posting to wall
    Ensures we have a valid URL and all required fields
    """
    try:
        discovery = discovery_data.get('discovery', {})
        bandcamp = discovery_data.get('bandcamp')
        
        # Priority 1: Use Bandcamp URL if available
        if bandcamp and bandcamp.get('url'):
            return {
                'url': bandcamp['url'],
                'artist': bandcamp.get('artist') or discovery.get('artist', ''),
                'album': bandcamp.get('album') or discovery.get('album', ''),
                'image_url': discovery.get('image')
            }
        
        # Priority 2: Use Spotify URL
        spotify_url = discovery.get('url', '')
        if spotify_url and 'open.spotify.com' in spotify_url:
            return {
                'url': spotify_url,
                'artist': discovery.get('artist', ''),
                'album': discovery.get('album', ''),
                'image_url': discovery.get('image')
            }
        
        # Priority 3: Use Last.fm URL
        artist_name = discovery.get('artist', '')
        if artist_name:
            # Create a Last.fm search URL
            lastfm_url = f"https://www.last.fm/music/{urllib.parse.quote(artist_name.replace(' ', '+'))}"
            return {
                'url': lastfm_url,
                'artist': artist_name,
                'album': discovery.get('album', ''),
                'image_url': discovery.get('image')
            }
        
        # Fallback: Use whatever we have
        return {
            'url': discovery.get('url', ''),
            'artist': discovery.get('artist', ''),
            'album': discovery.get('album', ''),
            'image_url': discovery.get('image')
        }
        
    except Exception as e:
        print(f"Error preparing discovery for posting: {e}")
        return {}

def discover_random_album(base_artist: Optional[str] = None, base_album_obj: Optional[Dict] = None, 
                         max_attempts: int = 8) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Main random discovery function with improved artist matching and metal validation
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
        
        # Step 2: Find related artists
        related_artists = []
        
        # Try Spotify first
        if spotify_client:
            related_artists = get_related_artists_spotify(spotify_client, base_artist_name_clean)
        
        # Try Last.fm if Spotify didn't find any or isn't available
        if not related_artists and lastfm_client:
            related_artists = get_related_artists_lastfm(lastfm_client, base_artist_name_clean)
        
        if not related_artists:
            return None, f"No related artists found for {base_artist_name_clean}"
        
        # Step 3: Filter out problematic related artists
        filtered_artists = filter_related_artists(related_artists, base_artist_name_clean)
        
        if not filtered_artists:
            # If filtering removed all, use original list but shuffle
            filtered_artists = related_artists.copy()
            random.shuffle(filtered_artists)
        
        # Try multiple attempts to find a valid metal album
        attempts = 0
        while attempts < max_attempts and filtered_artists:
            attempts += 1
            
            # Step 4: Pick random related artist from filtered list
            random_artist = random.choice(filtered_artists)
            
            # Remove this artist from list for next attempts
            filtered_artists.remove(random_artist)
            
            # Step 5: Get precise album from Spotify
            random_album_data = None
            if spotify_client:
                random_album_data = get_precise_spotify_album(spotify_client, random_artist)
            
            # If precise search fails, fall back to original method
            if not random_album_data and spotify_client:
                random_album_data = get_random_album_by_artist(spotify_client, random_artist)
            
            # If Spotify fails, create a basic discovery
            if not random_album_data:
                # Try to create a valid Last.fm URL
                lastfm_url = f"https://www.last.fm/music/{urllib.parse.quote(random_artist.replace(' ', '+'))}"
                random_album_data = {
                    "artist": random_artist,
                    "album": f"Random album by {random_artist}",
                    "image": None,
                    "url": lastfm_url,
                    "release_date": "Unknown",
                    "total_tracks": 0,
                    "genres": []
                }
            
            # Step 6: Validate it's a metal album
            if lastfm_client:
                validated_album, is_valid = validate_and_correct_metal_album(
                    lastfm_client, random_album_data
                )
                
                if is_valid and validated_album:
                    random_album_data = validated_album
                    
                    # Step 7: Try to find the album on Bandcamp
                    bandcamp_result = None
                    try:
                        bc_search_result = bandcamp_search(
                            random_album_data["artist"], 
                            random_album_data["album"]
                        )
                        if bc_search_result:
                            bandcamp_result = {
                                "url": bc_search_result["url"],
                                "artist": bc_search_result["artist"],
                                "album": bc_search_result["album"]
                            }
                    except Exception as e:
                        print(f"Bandcamp search failed: {e}")
                        pass
                    
                    # Prepare discovery data with all needed information
                    discovery_data = {
                        "origin": {
                            "album": random_album,
                            "artist": base_artist_name,
                            "album_name": base_album_name
                        },
                        "discovery": random_album_data,
                        "bandcamp": bandcamp_result,
                        "description": f"Based on '{base_album_name}' by {base_artist_name} → Related artist: {random_artist}",
                        "validation": "✅ Validated as metal",
                        # Add prepared posting data
                        "posting_data": prepare_discovery_for_posting({
                            "discovery": random_album_data,
                            "bandcamp": bandcamp_result
                        })
                    }
                    
                    # Save discovery to database if user is logged in
                    if st.session_state.get('current_user'):
                        save_discovery(
                            username=st.session_state.current_user,
                            base_artist=base_artist_name,
                            base_album=base_album_name,
                            discovered_artist=random_album_data["artist"],
                            discovered_album=random_album_data["album"],
                            discovered_url=random_album_data["url"],
                            cover_url=random_album_data.get("image")
                        )
                    
                    return discovery_data, None
                else:
                    # Not a metal album, try again
                    continue
            else:
                # No Last.fm client, can't validate - just return what we have
                bandcamp_result = None
                try:
                    if random_album_data:
                        bc_search_result = bandcamp_search(random_artist, random_album_data["album"])
                        if bc_search_result:
                            bandcamp_result = {
                                "url": bc_search_result["url"],
                                "artist": bc_search_result["artist"],
                                "album": bc_search_result["album"]
                            }
                except Exception as e:
                    print(f"Bandcamp search failed: {e}")
                    pass
                
                # Prepare discovery data with posting info
                discovery_data = {
                    "origin": {
                        "album": random_album,
                        "artist": base_artist_name,
                        "album_name": base_album_name
                    },
                    "discovery": random_album_data,
                    "bandcamp": bandcamp_result,
                    "description": f"Based on '{base_album_name}' by {base_artist_name} → Related artist: {random_artist}",
                    "validation": "⚠️ Could not validate (Last.fm not available)",
                    # Add prepared posting data
                    "posting_data": prepare_discovery_for_posting({
                        "discovery": random_album_data,
                        "bandcamp": bandcamp_result
                    })
                }
                
                return discovery_data, None
        
        # If we get here, we couldn't find a valid metal album after max attempts
        return None, f"Could not find a valid metal album after {max_attempts} attempts. Try again!"
        
    except Exception as e:
        return None, f"Error during discovery: {str(e)}"