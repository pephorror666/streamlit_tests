# File: metalwall_app/ui/pages.py
# ===========================
# PAGE RENDERING FUNCTIONS
# ===========================

import streamlit as st
import webbrowser
import re
from typing import List
from config import ADMIN_NAV_OPTIONS, USER_NAV_OPTIONS, SORT_OPTIONS
from ui.components import render_header, render_sidebar, render_album_post, render_concert_post
from database.operations import load_albums, load_concerts, delete_past_concerts, save_album, save_concert, check_duplicate_url
from services.metadata_extractor import extract_og_metadata
from services.random_album import discover_random_album
from utils.helpers import process_tags, show_success_message
from admin.backup_tools import admin_backup_page

def extract_metal_tags_from_discovery(discovery_data: dict) -> str:
    """
    Extract metal tags from discovery data and format them for posting
    Returns: string of tags (e.g., "#deathmetal #blackmetal #thrash")
    """
    if not discovery_data:
        return "#randomdiscovery"
    
    # First, try to get the pre-formatted tags
    formatted_tags = discovery_data.get('formatted_tags')
    if formatted_tags and formatted_tags != "#randomdiscovery":
        return formatted_tags
    
    # Fallback: try to get tags from multiple possible locations
    tags = []
    
    # 1. Check for metal_tags in discovery
    discovery = discovery_data.get('discovery', {})
    metal_tags = discovery.get('metal_tags', [])
    
    # 2. Check for lastfm_tags in discovery
    lastfm_tags = discovery.get('lastfm_tags', [])
    
    # 3. Check for lastfm_tags at the top level
    if not metal_tags and not lastfm_tags:
        lastfm_tags = discovery_data.get('lastfm_tags', [])
    
    # 4. Check for genres from Spotify
    spotify_genres = discovery.get('genres', [])
    
    # Prioritize metal tags from Last.fm
    if metal_tags:
        tags.extend(metal_tags)
    elif lastfm_tags:
        # Filter for metal-related tags only
        metal_keywords = ['metal', 'grind', 'metalcore', 'heavy', 'death', 'black', 'thrash', 
                         'doom', 'power', 'sludge', 'stoner', 'progressive', 'deathcore']
        
        for tag in lastfm_tags:
            tag_lower = tag.lower()
            if any(keyword in tag_lower for keyword in metal_keywords):
                tags.append(tag)
    
    # If we still don't have tags, check Spotify genres
    if not tags and spotify_genres:
        metal_keywords = ['metal', 'grind', 'metalcore', 'heavy', 'death', 'black', 'thrash']
        for genre in spotify_genres:
            genre_lower = genre.lower()
            if any(keyword in genre_lower for keyword in metal_keywords):
                tags.append(genre)
    
    # Clean and format tags
    cleaned_tags = []
    for tag in tags[:3]:  # Limit to 3 tags
        # Remove special characters and spaces, convert to lowercase
        cleaned = re.sub(r'[^\w\s]', '', tag)
        cleaned = cleaned.lower().replace(' ', '')
        
        # Ensure it's a valid tag (at least 2 characters)
        if len(cleaned) >= 2:
            # Capitalize first letter for better readability
            cleaned = cleaned.capitalize() if cleaned.islower() else cleaned
            cleaned_tags.append(f"#{cleaned}")
    
    # If no metal tags found, use default
    if not cleaned_tags:
        return "#randomdiscovery"
    
    # Return as space-separated string
    return ' '.join(cleaned_tags)

def main_page():
    """Main app function that handles page routing"""
    # Render header
    render_header()
    
    # Render sidebar and get selected page
    page = render_sidebar()
    
    # Route to appropriate page
    if page == "💿 Records":
        records_page()
    elif page == "🎸 Gigs":
        gigs_page()
    elif page == "🎲 Random Album":
        random_album_page()
    elif page == "👤 Profile":
        profile_page()
    elif page == "🔧 Admin Tools":
        if st.session_state.current_user == "Admin":
            admin_backup_page()
        else:
            st.error("⛔ Access Denied")
            st.warning("Only Admin users can access this section.")
            st.info("Please login with Admin credentials to access database tools.")

# ============ RECORDS PAGE ============

def records_page():
    """Records wall page"""
    st.subheader("💿 Records Wall")
    
    # Show guest notice if not logged in
    if not st.session_state.current_user:
        st.markdown("""
        <div class='guest-notice'>
        👀 You're browsing as a guest. You can view all content but need to 
        <strong><a href="#" onclick="window.location.href='?show_login=true'">login</a></strong> 
        to like, post, or delete content.
        </div>
        """, unsafe_allow_html=True)
    
    # Top bar with sorting and new post button
    render_records_top_bar()
    
    # Show album form if toggled
    if st.session_state.show_album_form and st.session_state.current_user:
        render_album_form()
    
    # Load and display albums
    render_albums_list()

def render_records_top_bar():
    """Render top bar for records page with sorting and new post button"""
    col_top1, col_top2, col_top3 = st.columns([3, 2, 1])
    
    with col_top1:
        st.markdown("**Sort by:**")
    
    with col_top2:
        # Sorting buttons
        sort_col1, sort_col2 = st.columns(2)
        with sort_col1:
            if st.button("📅 Timeline", 
                       key="sort_timeline",
                       use_container_width=True,
                       type="primary" if st.session_state.sort_option == "Timeline" else "secondary"):
                st.session_state.sort_option = "Timeline"
                st.rerun()
        with sort_col2:
            if st.button("👍 Votes", 
                       key="sort_votes",
                       use_container_width=True,
                       type="primary" if st.session_state.sort_option == "Votes" else "secondary"):
                st.session_state.sort_option = "Votes"
                st.rerun()
    
    with col_top3:
        # New Post button
        if st.session_state.current_user:
            if st.button("➕ New Post", key="new_post_button", use_container_width=True):
                st.session_state.show_album_form = not st.session_state.show_album_form
                st.rerun()
        else:
            st.button("➕ New Post", disabled=True, use_container_width=True,
                     help="Login to post albums")

def render_album_form():
    """Render album posting form"""
    st.markdown("---")
    st.subheader("🎵 New Album Post")
    
    # Show success message if form was just submitted
    if st.session_state.get('form_submitted'):
        st.success(st.session_state.success_message)
        st.session_state.form_submitted = False
    
    # Create two columns for the two input methods
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### Automatic (from URL)")
        st.write("Paste a Spotify, Deezer or Tidal URL")
        
        with st.form("album_form_auto", clear_on_submit=True):
            url = st.text_input("Album URL", placeholder="https://open.spotify.com/album/...")
            tags_input = st.text_input("Tags", placeholder="Example: #deathmetal #blackmetal #thrashmetal", 
                                     help="Maximum 5 tags")
            submitted_auto = st.form_submit_button("Post", use_container_width=True)
            
            if submitted_auto:
                handle_album_submission(url, tags_input)
    
    with col2:
        st.write("### Manual Input")
        st.write("For platforms without automatic metadata")
        
        with st.form("album_form_manual", clear_on_submit=True):
            artist = st.text_input("Artist", placeholder="Artist name")
            album_name = st.text_input("Album Name", placeholder="Album title")
            url = st.text_input("Album URL", placeholder="https://...")
            cover_url = st.text_input("Cover URL (optional)", placeholder="https://...")
            tags_input = st.text_input("Tags", placeholder="Example: #deathmetal #blackmetal #thrashmetal", 
                                     help="Maximum 5 tags")
            submitted_manual = st.form_submit_button("Post", use_container_width=True)
            
            if submitted_manual:
                handle_album_submission(url, tags_input, True, artist, album_name, cover_url)
    
    st.markdown("---")

def handle_album_submission(url: str, tags_input: str, is_manual: bool = False, 
                           artist: str = "", album_name: str = "", cover_url: str = ""):
    """Handle album form submission"""
    # Cover handeling
    if cover_url == "":
        cover_url = "https://upload.wikimedia.org/wikipedia/commons/3/3c/No-album-art.png"
    # Check for duplicate URL
    if check_duplicate_url(url):
        st.error("❌ This URL has already been posted. Please share a different album.")
        return False
    
    if is_manual:
        if artist and album_name and url:
            tags = process_tags(tags_input)
            if save_album(
                st.session_state.current_user,
                url,
                artist,
                album_name,
                cover_url,
                "Other",
                tags
            ):
                show_success_message("✅ Album shared successfully!")
                st.session_state.show_album_form = False
                # Force immediate refresh
                st.session_state.force_refresh = True
                st.rerun()
                return True
            else:
                st.error("❌ Error saving")
                return False
        else:
            st.warning("⚠️ Artist, Album Name, and Album URL are required")
            return False
    else:
        if url:
            with st.spinner("⏳ Extracting metadata..."):
                metadata = extract_og_metadata(url)
                if metadata:
                    tags = process_tags(tags_input)
                    if save_album(
                        st.session_state.current_user,
                        url,
                        metadata['artist'],
                        metadata['album_name'],
                        metadata['cover_url'],
                        metadata['platform'],
                        tags
                    ):
                        show_success_message("✅ Album shared successfully!")
                        st.session_state.show_album_form = False
                        # Force immediate refresh
                        st.session_state.force_refresh = True
                        st.rerun()
                        return True
                    else:
                        st.error("❌ Error saving")
                        return False
                else:
                    st.error("❌ Could not extract metadata. Verify the URL or use Manual Input")
                    return False
        else:
            st.warning("⚠️ Please paste a valid URL")
            return False

def render_albums_list():
    """Load and display albums with sorting and filtering"""
    # Force refresh if needed
    if st.session_state.get('force_refresh'):
        st.session_state.force_refresh = False
        # Clear any cached data
        if 'cached_albums' in st.session_state:
            del st.session_state.cached_albums
    
    albums = load_albums()
    
    # Apply sorting
    if st.session_state.sort_option == "Votes":
        albums = sorted(albums, key=lambda x: len(x.likes), reverse=True)
        show_rank = True
    else:
        # Timeline is the default (already sorted by timestamp in load_albums)
        show_rank = False
    
    # Apply tag filter if active
    if st.session_state.active_filter_feed:
        col_filter1, col_filter2 = st.columns([3, 1])
        with col_filter1:
            st.info(f"🔍 Filtered by: **#{st.session_state.active_filter_feed}**")
        with col_filter2:
            if st.button("✖️ Clear filter", key="clear_feed_filter", use_container_width=True):
                st.session_state.active_filter_feed = None
                st.rerun()
    
    if st.session_state.active_filter_feed:
        albums = [a for a in albums if st.session_state.active_filter_feed.lower() in [t.lower() for t in a.tags]]
    
    if not albums:
        st.info("📭 No albums to display")
    else:
        for idx, album in enumerate(albums, 1):
            if show_rank:
                render_album_post(album, show_rank=True, rank=idx)
            else:
                render_album_post(album)

# ============ GIGS PAGE ============

def gigs_page():
    """Gigs page"""
    st.subheader("🎸 Gigs")
    delete_past_concerts()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Upcoming metal events")
    with col2:
        # Only show New Concert button if user is logged in
        if st.session_state.current_user:
            if st.button("➕ New Concert", use_container_width=True):
                st.session_state.show_concert_form = not st.session_state.show_concert_form
        else:
            st.button("➕ New Concert", disabled=True, use_container_width=True,
                     help="Login to add concerts")
    
    if st.session_state.show_concert_form and st.session_state.current_user:
        render_concert_form()
    
    st.divider()
    render_concerts_list()

def render_concert_form():
    """Render concert posting form"""
    with st.form("concert_form", clear_on_submit=True):
        bands = st.text_input("Bands", placeholder="Separate with commas")
        date = st.date_input("Date")
        venue = st.text_input("Venue")
        city = st.text_input("City")
        tags_input = st.text_input("Tags", placeholder="Example: #deathmetal #liveshow")
        info = st.text_area("Additional info", placeholder="Tickets, prices, etc.")
        submitted = st.form_submit_button("✅ Save Concert", use_container_width=True)
        
        if submitted:
            if bands and venue and city:
                tags = process_tags(tags_input)
                if save_concert(st.session_state.current_user, bands, date, venue, city, tags, info):
                    show_success_message("✅ Concert added successfully!")
                    st.session_state.show_concert_form = False
                    st.rerun()
                else:
                    st.error("❌ Error saving")
            else:
                st.warning("⚠️ Please complete all required fields")

def render_concerts_list():
    """Load and display concerts"""
    concerts = load_concerts()
    
    if not concerts:
        st.info("📭 No upcoming concerts")
    else:
        for concert in concerts:
            render_concert_post(concert)

# ============ RANDOM ALBUM PAGE ============

def random_album_page():
    """Random Album discovery page"""
    st.subheader("🎲 Random Album Discovery")
    
    # Introduction
    st.markdown("""
    **Discover new music based on the albums in the wall!**
    """)
    
    st.divider()
    
    # Discover Button
    col_btn1, col_btn2 = st.columns([3, 1])
    
    with col_btn1:
        if st.button("🔍 Discover Random Album", 
                    use_container_width=True,
                    type="primary",
                    key="discover_main"):
            with st.spinner("🎲 Searching for your next musical discovery..."):
                discovery_data, error = discover_random_album()
                    
                if error:
                    st.error(f"❌ {error}")
                elif discovery_data:
                    st.session_state.random_discovery_data = discovery_data
                    st.rerun()
    
    # Display discovery if available
    if st.session_state.random_discovery_data:
        discovery_data = st.session_state.random_discovery_data
        
        # Discovery path
        st.markdown("<div class='discovery-path'>", unsafe_allow_html=True)
        st.markdown(f"**{discovery_data['description']}**")
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Show validation info if available
        if discovery_data.get('validation'):
            st.info(f"**Validation:** {discovery_data['validation']}")
        
        # Show tags if available
        discovery = discovery_data['discovery']
        if discovery.get('lastfm_tags'):
            # Extract metal tags
            metal_tags = []
            metal_keywords = ['metal', 'grind', 'metalcore', 'heavy', 'death', 'black', 'thrash']
            
            for tag in discovery['lastfm_tags'][:5]:  # Show top 5
                tag_lower = tag.lower()
                if any(keyword in tag_lower for keyword in metal_keywords):
                    metal_tags.append(tag)
            
            if metal_tags:
                tags_text = ', '.join(metal_tags[:3])
                st.caption(f"**Tags:** {tags_text}")
        
        # Album card
        st.markdown("<div class='random-album-card'>", unsafe_allow_html=True)
        
        col_img, col_info = st.columns([1, 2])
        
        with col_img:
            if discovery.get('image'):
                st.image(discovery['image'])
            else:
                st.markdown("""
                <div style="width:100%; height:200px; background:#333; 
                border-radius:8px; display:flex; align-items:center; 
                justify-content:center; color:#666;">
                🎵 No cover
                </div>
                """, unsafe_allow_html=True)
        
        with col_info:
            st.markdown(f"## {discovery['album']}")
            st.markdown(f"### by **{discovery['artist']}**")
            
            # Album details
            if discovery.get('release_date') and discovery['release_date'] != 'Unknown':
                st.write(f"**Released:** {discovery['release_date']}")
            
            if discovery.get('total_tracks') and discovery['total_tracks'] > 0:
                st.write(f"**Tracks:** {discovery['total_tracks']}")
            
            if discovery.get('genres'):
                st.write(f"**Genres:** {', '.join(discovery['genres'][:3])}")
            
            # Action buttons
            if discovery_data.get('bandcamp'):
                col_actions = st.columns([1, 1, 1, 1])
            else:
                col_actions = st.columns([1, 1, 1])
            
            col_idx = 0
            
            with col_actions[col_idx]:
                with col_actions[col_idx]:
                    st.link_button("🎵 Open in Spotify", discovery['url'], use_container_width=True)
            col_idx += 1
            
            # Add Bandcamp button if available
            if discovery_data.get('bandcamp'):
                with col_actions[col_idx]:
                    st.link_button("🎶 Open in Bandcamp", discovery_data['bandcamp']['url'], use_container_width=True)
                col_idx += 1
            
            with col_actions[col_idx]:
                if st.button("🔁 Discover Another", 
                           use_container_width=True,
                           key="discover_another"):
                    # Reuse the same base artist for new discovery
                    origin = discovery_data['origin']
                    new_discovery, error = discover_random_album(
                        base_artist=origin['artist'],
                        base_album_obj=origin['album']
                    )
                    if error:
                        st.error(f"❌ {error}")
                    else:
                        st.session_state.random_discovery_data = new_discovery
                    st.rerun()
            col_idx += 1
            
            with col_actions[col_idx]:
                if st.button("📤 Post to Wall", 
                        use_container_width=True,
                        key="post_to_wall"):
                    if st.session_state.current_user:
                        # Use the Last.fm tags for posting
                        url = discovery['url']
                        
                        # Extract metal tags from discovery data - use pre-formatted tags if available
                        tags_input = discovery_data.get('formatted_tags')
                        if not tags_input or tags_input == "#randomdiscovery":
                            tags_input = extract_metal_tags_from_discovery(discovery_data)
                        
                        # Show what tags will be used
                        if tags_input != "#randomdiscovery":
                            st.info(f"Using tags: {tags_input}")
                        
                        # Call the handle_album_submission function
                        success = handle_album_submission(url, tags_input, is_manual=False)
                        if success:
                            # Clear the discovery data to force a new discovery on next view
                            st.session_state.random_discovery_data = None
                            # Show success message and force refresh
                            st.success(f"✅ Album posted to wall!")
                            show_success_message("✅ Album posted successfully!")
                            # Force refresh to show the new post
                            st.rerun()
                        else:
                            st.error("❌ Failed to post to wall")
                    else:
                        st.warning("Please login to post to wall")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Show base album info
        origin = discovery_data['origin']
        if 'album' in origin:
            base_album = origin['album']
            st.markdown("---")
            st.markdown("**Based on this album from the wall:**")
            
            col_base1, col_base2 = st.columns([1, 3])
            
            with col_base1:
                if base_album.get('cover_url'):
                    st.image(base_album['cover_url'], width=80)
            
            with col_base2:
                st.markdown(f"**{base_album.get('artist', 'Unknown')}**")
                st.markdown(f"*{base_album.get('album_name', 'Unknown')}*")
                st.caption(f"Posted by @{base_album.get('username', 'Unknown')}")

# ============ PROFILE PAGE ============

def profile_page():
    """User profile page"""
    st.subheader("👤 Profile")
    
    if not st.session_state.current_user:
        st.info("""
        👤 **Your Profile**
        
        Login to see your profile, including:
        - Albums you've shared
        - Concerts you've added
        - Albums you've liked
        - Your discovery history
        - Your activity stats
        
        Use the login form in the sidebar to get started.
        """)
    else:
        albums = load_albums()
        concerts = load_concerts()
        my_albums = [a for a in albums if a.username == st.session_state.current_user]
        my_concerts = [c for c in concerts if c.username == st.session_state.current_user]
        
        # Get liked albums
        liked_albums = [a for a in albums if st.session_state.current_user in a.likes]
        
        # Show counts
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎵 My Albums", len(my_albums))
        with col2:
            st.metric("🎸 My Gigs", len(my_concerts))
        with col3:
            st.metric("❤️ Liked Albums", len(liked_albums))
        
        st.divider()
        
        if my_albums:
            st.write("### 🎵 My Albums")
            for album in my_albums:
                render_album_post(album)
        
        if liked_albums:
            st.write("### ❤️ Liked Albums")
            for album in liked_albums:
                render_album_post(album)
        
        if my_concerts:
            st.write("### 🎸 My Gigs")
            for concert in my_concerts:
                render_concert_post(concert)
        
        if not my_albums and not my_concerts and not liked_albums:
            st.info("📭 You haven't shared or liked anything yet")