# File: metalwall_app/services/metadata_extractor.py
# ===========================
# METADATA EXTRACTION SERVICE
# ===========================

import re
import requests
import urllib.parse
from bs4 import BeautifulSoup
from typing import Optional, Dict, List
from config import PLATFORMS

def get_headers_for_url(url: str) -> Dict[str, str]:
    """Get appropriate headers based on the platform"""
    url_lower = url.lower()
    
    if 'bandcamp' in url_lower:
        # Bandcamp-specific headers
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Referer': 'https://bandcamp.com/',
        }
    elif 'spotify' in url_lower:
        # Spotify-specific headers
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    elif 'deezer' in url_lower:
        # Deezer-specific headers
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.deezer.com/',
        }
    elif 'tidal' in url_lower:
        # Tidal-specific headers
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://tidal.com/',
        }
    else:
        # Generic headers for other platforms
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
    
    # Try common patterns
    patterns = [
        (r'(.+?) - (.+)', 2),  # "Artist - Album"
        (r'(.+?) by (.+)', 1),  # "Album by Artist"
        (r'(.+?) \| (.+)', 2),  # "Album | Artist"
        (r'(.+?) – (.+)', 2),  # "Artist – Album" (en dash)
    ]
    
    for pattern, group_idx in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(group_idx).strip()
    
    # Try description patterns
    if description:
        # Look for "by Artist" in description
        by_match = re.search(r'by ([^.,]+?)(?:\.|,|$)', description, re.IGNORECASE)
        if by_match:
            return by_match.group(1).strip()
        
        # Look for "Artist:" in description
        artist_match = re.search(r'Artist[:\s]+([^.,]+?)(?:\.|,|$)', description, re.IGNORECASE)
        if artist_match:
            return artist_match.group(1).strip()
    
    # Try to extract from title if it contains "by"
    if ' by ' in title.lower():
        parts = title.lower().split(' by ')
        if len(parts) >= 2:
            return parts[-1].strip().title()
    
    # Fallback: try to get the last part after a delimiter
    for delimiter in [' - ', ' | ', ' – ']:
        if delimiter in title:
            parts = title.split(delimiter)
            if len(parts) >= 2:
                # Usually the artist is the last part
                return parts[-1].strip()
    
    return 'Unknown Artist'

def extract_album(metadata: Dict, platform: str) -> str:
    """Extract album name from metadata"""
    title = metadata.get('og_title', '')
    
    # Try common patterns
    patterns = [
        (r'(.+?) - (.+)', 1),  # "Artist - Album"
        (r'(.+?) by (.+)', 1),  # "Album by Artist"
        (r'(.+?) \| (.+)', 1),  # "Album | Artist"
        (r'(.+?) – (.+)', 1),  # "Artist – Album" (en dash)
    ]
    
    for pattern, group_idx in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(group_idx).strip()
    
    # Try to extract from title if it contains "by"
    if ' by ' in title.lower():
        parts = title.lower().split(' by ')
        if len(parts) >= 2:
            return parts[0].strip()
    
    # Fallback: try to get the first part before a delimiter
    for delimiter in [' - ', ' | ', ' – ']:
        if delimiter in title:
            parts = title.split(delimiter)
            return parts[0].strip()
    
    return title or 'Unknown Album'

def extract_og_metadata(url: str) -> Optional[Dict]:
    """
    UNIVERSAL extractor using Open Graph metadata
    Works with ANY platform (Spotify, Bandcamp, Tidal, Apple Music, etc.)
    Similar to how WhatsApp/Discord/Twitter does it
    """
    try:
        # Clean and validate URL
        if not url or not url.startswith(('http://', 'https://')):
            print(f"Invalid URL: {url}")
            return None
        
        headers = get_headers_for_url(url)
        
        # Create session with headers
        session = requests.Session()
        session.headers.update(headers)
        
        # Set timeout based on platform
        timeout = 20 if 'bandcamp' in url.lower() else 10
        
        # Make the request
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"HTTP {response.status_code} for {url}")
            
            # Try with a different approach for Bandcamp
            if 'bandcamp' in url.lower():
                return try_bandcamp_fallback(url, session)
            
            # For Spotify, try without SSL verification
            if 'spotify' in url.lower():
                try:
                    response = session.get(url, timeout=timeout, allow_redirects=True, verify=False)
                    if response.status_code == 200:
                        # Continue with processing
                        pass
                except:
                    return None
            
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        metadata = {}
        
        # Look for Open Graph meta tags
        for meta in soup.find_all('meta', property=True):
            prop = meta.get('property', '').lower()
            content = meta.get('content', '')
            
            if prop == 'og:title':
                metadata['og_title'] = content
            elif prop == 'og:description':
                metadata['og_description'] = content
            elif prop == 'og:image':
                metadata['og_image'] = content
        
        # Fallback: look for Twitter meta tags
        if not metadata.get('og_title'):
            for meta in soup.find_all('meta'):
                name = meta.get('name', '').lower()
                content = meta.get('content', '')
                
                if name == 'twitter:title':
                    metadata['og_title'] = content
                elif name == 'twitter:description':
                    metadata['og_description'] = content
                elif name == 'twitter:image':
                    metadata['og_image'] = content
        
        # Fallback: look for regular meta tags
        if not metadata.get('og_title'):
            title_tag = soup.find('title')
            if title_tag:
                metadata['og_title'] = title_tag.text.strip()
            
            # Look for meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                metadata['og_description'] = meta_desc.get('content')
        
        # Special handling for Bandcamp if OG tags not found
        if not metadata.get('og_title') and 'bandcamp' in url.lower():
            bandcamp_metadata = extract_bandcamp_metadata(soup, url)
            if bandcamp_metadata:
                return bandcamp_metadata
        
        if not metadata.get('og_title'):
            print(f"No title found for {url}")
            return None
        
        platform_name = detect_platform(url)
        
        # Extract artist and album
        artist = extract_artist(metadata, platform_name)
        album_name = extract_album(metadata, platform_name)
        
        # Clean up extracted data
        if artist == 'Unknown Artist' and album_name == 'Unknown Album':
            # Try to parse from title more aggressively
            title = metadata.get('og_title', '')
            if ' - ' in title:
                parts = title.split(' - ')
                if len(parts) >= 2:
                    artist = parts[0].strip()
                    album_name = parts[1].strip()
        
        # Get cover URL
        cover_url = metadata.get('og_image', '')
        
        # If no cover URL but we have Bandcamp, try to find it
        if not cover_url and 'bandcamp' in url.lower():
            cover_url = find_bandcamp_cover(soup)
        
        return {
            'artist': artist,
            'album_name': album_name,
            'cover_url': cover_url,
            'platform': platform_name
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

def find_bandcamp_cover(soup: BeautifulSoup) -> str:
    """Find cover image in Bandcamp page"""
    try:
        # Look for track art
        track_art = soup.find('a', class_='popupImage')
        if track_art and track_art.get('href'):
            return track_art['href']
        
        # Look for album art
        album_art = soup.find('img', id='tralbumArt')
        if album_art and album_art.get('src'):
            return album_art['src']
        
        # Look for any image with class containing 'art'
        for img in soup.find_all('img', class_=lambda x: x and 'art' in x.lower()):
            if img.get('src'):
                return img['src']
        
        # Look for og:image in meta tags
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image.get('content')
        
        # Look for any image that might be a cover
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                if 'cover' in src.lower() or 'album' in src.lower():
                    return src
        
    except Exception as e:
        print(f"Error finding Bandcamp cover: {e}")
    
    return ''

def extract_bandcamp_metadata(soup: BeautifulSoup, url: str) -> Optional[Dict]:
    """Extract metadata specifically from Bandcamp pages"""
    try:
        # Try to get title from <title> tag
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else ''
        
        # Try to get artist and album from title
        artist = 'Unknown Artist'
        album_name = 'Unknown Album'
        
        if ' | ' in title:
            parts = title.split(' | ')
            if len(parts) >= 2:
                # Format is usually "Album Name | Artist Name | Bandcamp"
                album_name = parts[0].strip()
                artist = parts[1].strip()
        elif ' by ' in title.lower():
            parts = title.lower().split(' by ')
            if len(parts) >= 2:
                album_name = parts[0].strip()
                artist = parts[1].replace('| bandcamp', '').strip().title()
        elif ' - ' in title:
            parts = title.split(' - ')
            if len(parts) >= 2:
                artist = parts[0].strip()
                album_name = parts[1].strip()
        
        # Try to get cover image
        cover_url = find_bandcamp_cover(soup)
        
        # Clean up artist name
        if artist.lower().endswith('| bandcamp'):
            artist = artist[:-10].strip()
        
        return {
            'artist': artist,
            'album_name': album_name,
            'cover_url': cover_url,
            'platform': 'Bandcamp'
        }
    except Exception as e:
        print(f"Error extracting Bandcamp metadata: {e}")
        return None

def try_bandcamp_fallback(url: str, session: requests.Session) -> Optional[Dict]:
    """Try alternative methods for Bandcamp"""
    try:
        # Try with mobile user agent
        mobile_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://bandcamp.com/',
        }
        
        session.headers.update(mobile_headers)
        response = session.get(url, timeout=20, allow_redirects=True)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            return extract_bandcamp_metadata(soup, url)
    
    except Exception as e:
        print(f"Bandcamp fallback failed: {e}")
    
    return None