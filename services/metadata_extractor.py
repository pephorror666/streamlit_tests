# File: metalwall_app/services/metadata_extractor.py
# ===========================
# METADATA EXTRACTION SERVICE
# ===========================

import re
import requests
import json
import time
import random
from bs4 import BeautifulSoup
from typing import Optional, Dict, List
from config import PLATFORMS

def get_bandcamp_headers() -> Dict[str, str]:
    """Get comprehensive headers for Bandcamp requests"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]
    
    accept_languages = [
        'en-US,en;q=0.9',
        'en-GB,en;q=0.8,en-US;q=0.7',
        'en-CA,en;q=0.9,fr-CA;q=0.8,fr;q=0.7',
        'en-AU,en;q=0.9',
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': random.choice(accept_languages),
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Referer': 'https://bandcamp.com/',
        'Origin': 'https://bandcamp.com',
    }

def get_headers_for_url(url: str) -> Dict[str, str]:
    """Get appropriate headers based on the platform"""
    url_lower = url.lower()
    
    if 'bandcamp' in url_lower:
        return get_bandcamp_headers()
    elif 'spotify' in url_lower:
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    else:
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

def detect_platform(url: str) -> str:
    """Detect platform based on domain"""
    url_lower = url.lower()
    for key, value in PLATFORMS.items():
        if key in url_lower:
            return value
    return 'Other'

def extract_artist(metadata: Dict, platform: str) -> str:
    """Extract artist name from metadata"""
    title = metadata.get('og_title', '')
    description = metadata.get('og_description', '')
    
    if ' - ' in title:
        parts = title.split(' - ')
        if len(parts) >= 2:
            return parts[-1].strip()
    
    if 'by' in description:
        match = re.search(r'by (.+?)$|by (.+?) on', description, re.IGNORECASE)
        if match:
            return match.group(1) or match.group(2)
    
    if ' by ' in title:
        return title.split(' by ')[-1].strip()
    
    return 'Unknown Artist'

def extract_album(metadata: Dict, platform: str) -> str:
    """Extract album name from metadata"""
    title = metadata.get('og_title', '')
    
    if ' - ' in title:
        parts = title.split(' - ')
        return parts[0].strip()
    
    if ' by ' in title:
        return title.split(' by ')[0].strip()
    
    return title or 'Unknown Album'

# ==================== BANDCAMP-SPECIFIC EXTRACTION ====================

def extract_bandcamp_metadata_advanced(url: str) -> Optional[Dict]:
    """
    Advanced Bandcamp metadata extraction with multiple fallback methods
    """
    methods = [
        _extract_bandcamp_via_og_tags,
        _extract_bandcamp_via_json_ld,
        _extract_bandcamp_via_js_data,
        _extract_bandcamp_via_html_structure,
        _extract_bandcamp_via_api,
    ]
    
    for method in methods:
        try:
            result = method(url)
            if result and result.get('artist') and result.get('artist') != 'Unknown Artist':
                result['platform'] = 'Bandcamp'
                return result
        except Exception as e:
            print(f"Bandcamp method {method.__name__} failed: {e}")
            continue
    
    return None

def _extract_bandcamp_via_og_tags(url: str) -> Optional[Dict]:
    """Extract metadata using Open Graph tags"""
    try:
        session = requests.Session()
        session.headers.update(get_bandcamp_headers())
        
        # Add small delay to appear more human-like
        time.sleep(random.uniform(0.5, 1.5))
        
        response = session.get(url, timeout=20, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract Open Graph metadata
        metadata = {}
        og_title = soup.find('meta', property='og:title')
        og_description = soup.find('meta', property='og:description')
        og_image = soup.find('meta', property='og:image')
        
        if og_title:
            metadata['og_title'] = og_title.get('content', '')
        if og_description:
            metadata['og_description'] = og_description.get('content', '')
        if og_image:
            metadata['og_image'] = og_image.get('content', '')
        
        # If we have OG data, process it
        if metadata.get('og_title'):
            return {
                'artist': extract_artist(metadata, 'Bandcamp'),
                'album_name': extract_album(metadata, 'Bandcamp'),
                'cover_url': metadata.get('og_image', ''),
            }
    
    except Exception as e:
        print(f"OG extraction failed: {e}")
    
    return None

def _extract_bandcamp_via_json_ld(url: str) -> Optional[Dict]:
    """Extract metadata using JSON-LD structured data"""
    try:
        session = requests.Session()
        session.headers.update(get_bandcamp_headers())
        
        response = session.get(url, timeout=20, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for JSON-LD script tags
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                
                # Check for MusicAlbum or MusicRecording schema
                if isinstance(data, dict) and data.get('@type') in ['MusicAlbum', 'MusicRecording']:
                    result = {}
                    
                    # Extract artist
                    if data.get('byArtist'):
                        if isinstance(data['byArtist'], dict):
                            result['artist'] = data['byArtist'].get('name', 'Unknown Artist')
                        elif isinstance(data['byArtist'], str):
                            result['artist'] = data['byArtist']
                    
                    # Extract album/track name
                    if data.get('name'):
                        result['album_name'] = data['name']
                    
                    # Extract image
                    if data.get('image'):
                        if isinstance(data['image'], str):
                            result['cover_url'] = data['image']
                        elif isinstance(data['image'], dict):
                            result['cover_url'] = data['image'].get('url', '')
                        elif isinstance(data['image'], list) and len(data['image']) > 0:
                            result['cover_url'] = data['image'][0] if isinstance(data['image'][0], str) else data['image'][0].get('url', '')
                    
                    if result.get('artist') and result.get('album_name'):
                        return result
                        
            except json.JSONDecodeError:
                continue
    
    except Exception as e:
        print(f"JSON-LD extraction failed: {e}")
    
    return None

def _extract_bandcamp_via_js_data(url: str) -> Optional[Dict]:
    """Extract metadata from embedded JavaScript data"""
    try:
        session = requests.Session()
        session.headers.update(get_bandcamp_headers())
        
        response = session.get(url, timeout=20, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for TralbumData (Bandcamp's internal data structure)
        for script in soup.find_all('script'):
            if script.string and 'TralbumData' in script.string:
                # Extract the JSON object
                matches = re.findall(r'TralbumData\s*=\s*({[^;]+});', script.string)
                for match in matches:
                    try:
                        # Clean up the JSON string
                        json_str = re.sub(r'//.*?\n', '\n', match)  # Remove comments
                        data = json.loads(json_str)
                        
                        result = {}
                        
                        # Extract artist
                        if data.get('artist'):
                            result['artist'] = data['artist']
                        
                        # Extract album/track name
                        if data.get('current') and data['current'].get('title'):
                            result['album_name'] = data['current']['title']
                        elif data.get('album_title'):
                            result['album_name'] = data['album_title']
                        
                        # Extract cover image from art_id
                        if data.get('art_id'):
                            # Construct cover URL from art_id
                            art_id = str(data['art_id'])
                            result['cover_url'] = f"https://f4.bcbits.com/img/a{art_id}_16.jpg"
                        
                        if result.get('artist') and result.get('album_name'):
                            return result
                            
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        # Alternative: Look for data attributes
        for div in soup.find_all('div', attrs={'data-item-id': True}):
            data_artist = div.get('data-artist')
            data_album = div.get('data-item-title')
            
            if data_artist and data_album:
                result = {
                    'artist': data_artist,
                    'album_name': data_album,
                    'cover_url': '',
                }
                
                # Try to find image
                img = div.find('img', src=True)
                if img:
                    result['cover_url'] = img['src']
                
                return result
    
    except Exception as e:
        print(f"JS data extraction failed: {e}")
    
    return None

def _extract_bandcamp_via_html_structure(url: str) -> Optional[Dict]:
    """Extract metadata from HTML structure"""
    try:
        session = requests.Session()
        session.headers.update(get_bandcamp_headers())
        
        response = session.get(url, timeout=20, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        result = {
            'artist': 'Unknown Artist',
            'album_name': 'Unknown Album',
            'cover_url': '',
        }
        
        # Method 1: Try to get from title tag
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.text.strip()
            # Common patterns: "Album Name | Artist Name | Bandcamp"
            if ' | ' in title:
                parts = [p.strip() for p in title.split('|')]
                if len(parts) >= 2:
                    result['album_name'] = parts[0]
                    result['artist'] = parts[1]
        
        # Method 2: Try to get artist from specific selectors
        artist_selectors = [
            'span[itemprop="byArtist"]',
            '.artist',
            '.band-name',
            '.trackTitle span a',
            'h3 span a',
            '.title-artist a',
        ]
        
        for selector in artist_selectors:
            element = soup.select_one(selector)
            if element and element.text.strip():
                result['artist'] = element.text.strip()
                break
        
        # Method 3: Try to get album name from specific selectors
        album_selectors = [
            'h2.trackTitle',
            '.trackTitle',
            '.album-title',
            '[itemprop="name"]',
            'h2',
        ]
        
        for selector in album_selectors:
            element = soup.select_one(selector)
            if element and element.text.strip():
                result['album_name'] = element.text.strip()
                break
        
        # Method 4: Try to get cover image
        cover_selectors = [
            'a.popupImage',
            '#tralbumArt',
            '.album-art img',
            '.art img',
            '[itemprop="image"]',
            'img.album-cover',
        ]
        
        for selector in cover_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'a' and element.get('href'):
                    result['cover_url'] = element['href']
                    break
                elif element.name == 'img' and element.get('src'):
                    result['cover_url'] = element['src']
                    break
        
        if result['artist'] != 'Unknown Artist' and result['album_name'] != 'Unknown Album':
            return result
    
    except Exception as e:
        print(f"HTML structure extraction failed: {e}")
    
    return None

def _extract_bandcamp_via_api(url: str) -> Optional[Dict]:
    """
    Try to use Bandcamp's API endpoints if available
    This is a more direct approach that might bypass some restrictions
    """
    try:
        # Extract album/track ID from URL
        # Bandcamp URLs often have patterns like:
        # https://artist.bandcamp.com/album/album-name
        # https://artist.bandcamp.com/track/track-name
        
        # Try to get the basic info endpoint
        session = requests.Session()
        session.headers.update(get_bandcamp_headers())
        
        # Try to fetch the page with a mobile user-agent
        mobile_headers = get_bandcamp_headers()
        mobile_headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'
        session.headers.update(mobile_headers)
        
        response = session.get(url, timeout=30, allow_redirects=True)
        
        if response.status_code == 200:
            # Try to parse as before
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for meta tags in the mobile version
            metadata = {}
            for meta in soup.find_all('meta'):
                prop = meta.get('property', '')
                name = meta.get('name', '')
                content = meta.get('content', '')
                
                if prop in ['og:title', 'twitter:title']:
                    metadata['og_title'] = content
                elif prop in ['og:description', 'twitter:description']:
                    metadata['og_description'] = content
                elif prop in ['og:image', 'twitter:image']:
                    metadata['og_image'] = content
            
            if metadata.get('og_title'):
                return {
                    'artist': extract_artist(metadata, 'Bandcamp'),
                    'album_name': extract_album(metadata, 'Bandcamp'),
                    'cover_url': metadata.get('og_image', ''),
                }
    
    except Exception as e:
        print(f"API extraction failed: {e}")
    
    return None

def extract_og_metadata(url: str) -> Optional[Dict]:
    """
    UNIVERSAL extractor using Open Graph metadata
    Works with ANY platform (Spotify, Bandcamp, Tidal, Apple Music, etc.)
    Similar to how WhatsApp/Discord/Twitter does it
    """
    try:
        url_lower = url.lower()
        
        # Special handling for Bandcamp
        if 'bandcamp' in url_lower:
            # Try the advanced Bandcamp extraction first
            result = extract_bandcamp_metadata_advanced(url)
            if result:
                return result
        
        # For other platforms, use the standard approach
        headers = get_headers_for_url(url)
        
        session = requests.Session()
        session.headers.update(headers)
        
        timeout = 30 if 'bandcamp' in url_lower else 10
        
        # Add random delay for Bandcamp to avoid rate limiting
        if 'bandcamp' in url_lower:
            time.sleep(random.uniform(1, 3))
        
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"HTTP {response.status_code} for {url}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        metadata = {}
        
        # Look for Open Graph meta tags
        for meta in soup.find_all('meta', property=True):
            prop = meta.get('property', '')
            content = meta.get('content', '')
            if prop == 'og:title':
                metadata['og_title'] = content
            elif prop == 'og:description':
                metadata['og_description'] = content
            elif prop == 'og:image':
                metadata['og_image'] = content
        
        # Fallback: look for meta name
        if not metadata.get('og_title'):
            for meta in soup.find_all('meta'):
                name = meta.get('name', '')
                content = meta.get('content', '')
                if name.lower() == 'description':
                    metadata['og_description'] = content
                elif name.lower() == 'twitter:title':
                    metadata['og_title'] = content
                elif name.lower() == 'twitter:image':
                    metadata['og_image'] = content
        
        # Special handling for Bandcamp (fallback if advanced method failed)
        if not metadata.get('og_title') and 'bandcamp' in url_lower:
            # Try one more time with a different approach
            return extract_bandcamp_metadata_advanced(url)
        
        if not metadata.get('og_title'):
            # Try to get from title tag as last resort
            title_tag = soup.find('title')
            if title_tag:
                metadata['og_title'] = title_tag.text.strip()
            else:
                return None
        
        platform = detect_platform(url)
        return {
            'artist': extract_artist(metadata, platform),
            'album_name': extract_album(metadata, platform),
            'cover_url': metadata.get('og_image', ''),
            'platform': platform
        }
        
    except requests.exceptions.Timeout:
        print(f"Timeout for {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request error for {url}: {e}")
        return None
    except Exception as e:
        print(f"Error extracting metadata from {url}: {e}")
        return None