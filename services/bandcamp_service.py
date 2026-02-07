# File: metalwall_app/services/bandcamp_service.py
# ===========================
# BANDCAMP SERVICE
# ===========================

import requests
import time
import random
from bs4 import BeautifulSoup
from typing import Optional, Dict

def get_bandcamp_search_headers() -> Dict[str, str]:
    """Get headers specifically for Bandcamp search"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'no-cache',
        'Referer': 'https://bandcamp.com/',
    }

def bandcamp_search(artist: str, record: str) -> Optional[Dict]:
    """Scrape Bandcamp search results and return first match"""
    try:
        # Add delay to avoid rate limiting
        time.sleep(random.uniform(1, 2))
        
        # Clean and encode search query
        q = f"{artist} {record}".strip()
        encoded_q = requests.utils.quote(q)
        url = f"https://bandcamp.com/search?q={encoded_q}&item_type=a"
        
        # Use session with headers
        session = requests.Session()
        session.headers.update(get_bandcamp_search_headers())
        
        res = session.get(url, timeout=20)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Try multiple selectors for search results
        selectors = [
            "li.searchresult", 
            ".searchresult", 
            ".search-item", 
            ".result-item"
        ]
        
        result = None
        for selector in selectors:
            li = soup.select_one(selector)
            if li:
                result = li
                break
        
        if not result:
            return None
        
        # Extract link
        a_tag = result.find('a', href=True)
        if not a_tag:
            return None
        
        # Extract title and artist
        heading = result.find('div', class_='heading') or result.find('h2') or result.find('h3')
        subhead = result.find('div', class_='subhead') or result.find('div', class_='artist') or result.find('p')
        
        if a_tag and heading:
            clean_url = a_tag["href"].split("?")[0]
            
            # Make sure URL is absolute
            if clean_url.startswith('/'):
                clean_url = f"https://bandcamp.com{clean_url}"
            
            artist_name = subhead.text.replace('by ', '').strip() if subhead else artist
            album_name = heading.text.strip()
            
            return {
                "artist": artist_name,
                "album": album_name,
                "url": clean_url,
            }
            
    except Exception as e:
        print(f"Error searching Bandcamp: {e}")
        return None