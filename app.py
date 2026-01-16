import sys
import subprocess
import threading
import time
import os
import json
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import urllib.parse
import requests
import sqlite3
from pathlib import Patch

# Install required packages
try:
    import streamlit as st
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit"])
    import streamlit as st

try:
    import google.auth
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import Flow
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-auth", "google-auth-oauthlib", "google-api-python-client"])
    import google.auth
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import Flow

# Predefined OAuth configuration
PREDEFINED_OAUTH_CONFIG = {
    "web": {
        "client_id": "1086578184958-hin4d45sit9ma5psovppiq543eho41sl.apps.googleusercontent.com",
        "project_id": "anjelikakozme",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": ["https://livenews1x.streamlit.app"]
    }
}

# Initialize database for persistent logs
def init_database():
    """Initialize SQLite database for persistent logs"""
    try:
        db_path = Path("streaming_logs.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streaming_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                log_type TEXT NOT NULL,
                message TEXT NOT NULL,
                video_file TEXT,
                stream_key TEXT,
                channel_name TEXT
            )
        ''')
        
        # Create streaming_sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streaming_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                video_file TEXT,
                stream_title TEXT,
                stream_description TEXT,
                tags TEXT,
                category TEXT,
                privacy_status TEXT,
                made_for_kids BOOLEAN,
                channel_name TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Create saved_channels table for persistent authentication
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT UNIQUE NOT NULL,
                channel_id TEXT NOT NULL,
                auth_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Database initialization error: {e}")

def save_channel_auth(channel_name, channel_id, auth_data):
    """Save channel authentication data persistently"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO saved_channels 
            (channel_name, channel_id, auth_data, created_at, last_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            channel_name,
            channel_id,
            json.dumps(auth_data),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error saving channel auth: {e}")
        return False

def load_saved_channels():
    """Load saved channel authentication data"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT channel_name, channel_id, auth_data, last_used
            FROM saved_channels 
            ORDER BY last_used DESC
        ''')
        
        channels = []
        for row in cursor.fetchall():
            channel_name, channel_id, auth_data, last_used = row
            channels.append({
                'name': channel_name,
                'id': channel_id,
                'auth': json.loads(auth_data),
                'last_used': last_used
            })
        
        conn.close()
        return channels
    except Exception as e:
        st.error(f"Error loading saved channels: {e}")
        return []

def update_channel_last_used(channel_name):
    """Update last used timestamp for a channel"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE saved_channels 
            SET last_used = ?
            WHERE channel_name = ?
        ''', (datetime.now().isoformat(), channel_name))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error updating channel last used: {e}")

def log_to_database(session_id, log_type, message, video_file=None, stream_key=None, channel_name=None):
    """Log message to database"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO streaming_logs 
            (timestamp, session_id, log_type, message, video_file, stream_key, channel_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            session_id,
            log_type,
            message,
            video_file,
            stream_key,
            channel_name
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error logging to database: {e}")

def get_logs_from_database(session_id=None, limit=100):
    """Get logs from database"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        if session_id:
            cursor.execute('''
                SELECT timestamp, log_type, message, video_file, channel_name
                FROM streaming_logs 
                WHERE session_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (session_id, limit))
        else:
            cursor.execute('''
                SELECT timestamp, log_type, message, video_file, channel_name
                FROM streaming_logs 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
        
        logs = cursor.fetchall()
        conn.close()
        return logs
    except Exception as e:
        st.error(f"Error getting logs from database: {e}")
        return []

def save_streaming_session(session_id, video_file, stream_title, stream_description, tags, category, privacy_status, made_for_kids, channel_name):
    """Save streaming session to database"""
    try:
        conn = sqlite3.connect("streaming_logs.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO streaming_sessions 
            (session_id, start_time, video_file, stream_title, stream_description, tags, category, privacy_status, made_for_kids, channel_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            datetime.now().isoformat(),
            video_file,
            stream_title,
            stream_description,
            tags,
            category,
            privacy_status,
            made_for_kids,
            channel_name
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Error saving streaming session: {e}")

def load_google_oauth_config(json_file):
    """Load Google OAuth configuration from downloaded JSON file"""
    try:
        config = json.load(json_file)
        if 'web' in config:
            return config['web']
        elif 'installed' in config:
            return config['installed']
        else:
            st.error("Invalid Google OAuth JSON format")
            return None
    except Exception as e:
        st.error(f"Error loading Google OAuth JSON: {e}")
        return None

def generate_auth_url(client_config):
    """Generate OAuth authorization URL"""
    try:
        scopes = ['https://www.googleapis.com/auth/youtube.force-ssl']
        
        # Create authorization URL
        auth_url = (
            f"{client_config['auth_uri']}?"
            f"client_id={client_config['client_id']}&"
            f"redirect_uri={urllib.parse.quote(client_config['redirect_uris'][0])}&"
            f"scope={urllib.parse.quote(' '.join(scopes))}&"
            f"response_type=code&"
            f"access_type=offline&"
            f"prompt=consent"
        )
        return auth_url
    except Exception as e:
        st.error(f"Error generating auth URL: {e}")
        return None

def exchange_code_for_tokens(client_config, auth_code):
    """Exchange authorization code for access and refresh tokens"""
    try:
        token_data = {
            'client_id': client_config['client_id'],
            'client_secret': client_config['client_secret'],
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': client_config['redirect_uris'][0]
        }
        
        response = requests.post(client_config['token_uri'], data=token_data)
        
        if response.status_code == 200:
            tokens = response.json()
            return tokens
        else:
            st.error(f"Token exchange failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error exchanging code for tokens: {e}")
        return None

def load_channel_config(json_file):
    """Load channel configuration from JSON file"""
    try:
        config = json.load(json_file)
        return config
    except Exception as e:
        st.error(f"Error loading JSON file: {e}")
        return None

def validate_channel_config(config):
    """Validate channel configuration structure"""
    required_fields = ['channels']
    for field in required_fields:
        if field not in config:
            return False, f"Missing required field: {field}"
    
    if not isinstance(config['channels'], list):
        return False, "Channels must be a list"
    
    for i, channel in enumerate(config['channels']):
        required_channel_fields = ['name', 'stream_key']
        for field in required_channel_fields:
            if field not in channel:
                return False, f"Channel {i+1} missing required field: {field}"
    
    return True, "Valid configuration"

def create_youtube_service(credentials_dict):
    """Create YouTube API service from credentials"""
    try:
        if 'token' in credentials_dict:
            credentials = Credentials.from_authorized_user_info(credentials_dict)
        else:
            credentials = Credentials(
                token=credentials_dict.get('access_token'),
                refresh_token=credentials_dict.get('refresh_token'),
                token_uri=credentials_dict.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=credentials_dict.get('client_id'),
                client_secret=credentials_dict.get('client_secret'),
                scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
            )
        service = build('youtube', 'v3', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Error creating YouTube service: {e}")
        return None

def get_stream_key_only(service):
    """Get stream key without creating broadcast"""
    try:
        # Create a simple live stream to get stream key
        stream_request = service.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {
                    "title": f"Stream Key Generator - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
                },
                "cdn": {
                    "resolution": "1080p",
                    "frameRate": "30fps",
                    "ingestionType": "rtmp"
                }
            }
        )
        stream_response = stream_request.execute()
        
        return {
            "stream_key": stream_response['cdn']['ingestionInfo']['streamName'],
            "stream_url": stream_response['cdn']['ingestionInfo']['ingestionAddress'],
            "stream_id": stream_response['id']
        }
    except Exception as e:
        st.error(f"Error getting stream key: {e}")
        return None

def get_channel_info(service, channel_id=None):
    """Get channel information from YouTube API"""
    try:
        if channel_id:
            request = service.channels().list(
                part="snippet,statistics",
                id=channel_id
            )
        else:
            request = service.channels().list(
                part="snippet,statistics",
                mine=True
            )
        
        response = request.execute()
        return response.get('items', [])
    except Exception as e:
        st.error(f"Error fetching channel info: {e}")
        return []

def create_live_stream(service, title, description, scheduled_start_time, tags=None, category_id="20", privacy_status="public", made_for_kids=False):
    """Create a live stream on YouTube with complete settings"""
    try:
        # Create live stream
        stream_request = service.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {
                    "title": f"{title} - Stream",
                    "description": description
                },
                "cdn": {
                    "resolution": "1080p",
                    "frameRate": "30fps",
                    "ingestionType": "rtmp"
                }
            }
        )
        stream_response = stream_request.execute()
        
        # Prepare broadcast body
        broadcast_body = {
            "snippet": {
                "title": title,
                "description": description,
                "scheduledStartTime": scheduled_start_time.isoformat()
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
                "enableAutoStart": True,  # Auto start live stream
                "enableAutoStop": True    # Auto stop when video ends
            },
            "contentDetails": {
                "enableAutoStart": True,
                "enableAutoStop": True,
                "recordFromStart": True,
                "enableContentEncryption": False,
                "enableEmbed": True,
                "enableDvr": True,
                "enableLowLatency": False
            }
        }
        
        # Add tags if provided
        if tags:
            broadcast_body["snippet"]["tags"] = tags
            
        # Add category if provided
        if category_id:
            broadcast_body["snippet"]["categoryId"] = category_id
        
        # Create live broadcast
        broadcast_request = service.liveBroadcasts().insert(
            part="snippet,status,contentDetails",
            body=broadcast_body
        )
        broadcast_response = broadcast_request.execute()
        
        # Bind stream to broadcast
        bind_request = service.liveBroadcasts().bind(
            part="id,contentDetails",
            id=broadcast_response['id'],
            streamId=stream_response['id']
        )
        bind_response = bind_request.execute()
        
        return {
            "stream_key": stream_response['cdn']['ingestionInfo']['streamName'],
            "stream_url": stream_response['cdn']['ingestionInfo']['ingestionAddress'],
            "broadcast_id": broadcast_response['id'],
            "stream_id": stream_response['id'],
            "watch_url": f"https://www.youtube.com/watch?v={broadcast_response['id']}",
            "studio_url": f"https://studio.youtube.com/video/{broadcast_response['id']}/livestreaming",
            "broadcast_response": broadcast_response
        }
    except Exception as e:
        st.error(f"Error creating live stream: {e}")
        return None

def get_existing_broadcasts(service, max_results=10):
    """Get existing live broadcasts"""
    try:
        request = service.liveBroadcasts().list(
            part="snippet,status,contentDetails",
            mine=True,
            maxResults=max_results,
            broadcastStatus="all"
        )
        response = request.execute()
        return response.get('items', [])
    except Exception as e:
        st.error(f"Error getting existing broadcasts: {e}")
        return []

def get_broadcast_stream_key(service, broadcast_id):
    """Get stream key for existing broadcast"""
    try:
        # Get broadcast details
        broadcast_request = service.liveBroadcasts().list(
            part="contentDetails",
            id=broadcast_id
        )
        broadcast_response = broadcast_request.execute()
        
        if not broadcast_response['items']:
            return None
            
        stream_id = broadcast_response['items'][0]['contentDetails'].get('boundStreamId')
        
        if not stream_id:
            return None
            
        # Get stream details
        stream_request = service.liveStreams().list(
            part="cdn",
            id=stream_id
        )
        stream_response = stream_request.execute()
        
        if stream_response['items']:
            stream_info = stream_response['items'][0]['cdn']['ingestionInfo']
            return {
                "stream_key": stream_info['streamName'],
                "stream_url": stream_info['ingestionAddress'],
                "stream_id": stream_id
            }
        
        return None
    except Exception as e:
        st.error(f"Error getting broadcast stream key: {e}")
        return None

def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True,
            text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        st.warning(f"Tidak dapat membaca durasi video: {e}")
        return None

def run_ffmpeg(video_path, stream_key, is_shorts, log_callback, rtmp_url=None, session_id=None, duration_limit=None):
    """Run FFmpeg for streaming with optional duration limit."""
    output_url = rtmp_url or f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
    scale = "-vf scale=720:1280" if is_shorts else ""
    
    cmd = [
        "ffmpeg", "-re", "-stream_loop", "-1", "-i", video_path,
        "-c:v", "libx264", "-preset", "veryfast", "-b:v", "2500k",
        "-maxrate", "2500k", "-bufsize", "5000k",
        "-g", "60", "-keyint_min", "60",
        "-c:a", "aac", "-b:a", "128k",
        "-f", "flv"
    ]
    
    if duration_limit:
        cmd.insert(1, str(duration_limit))
        cmd.insert(1, "-t")

    if scale:
        cmd += scale.split()
    cmd.append(output_url)
    
    start_msg = f"🚀 Starting FFmpeg: {' '.join(cmd[:8])}... [RTMP URL hidden for security]"
    log_callback(start_msg)
    if session_id:
        log_to_database(session_id, "INFO", start_msg, video_path)
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            log_callback(line.strip())
            if session_id:
                log_to_database(session_id, "FFMPEG", line.strip(), video_path)
        process.wait()
        
        end_msg = "✅ Streaming completed successfully"
        log_callback(end_msg)
        if session_id:
            log_to_database(session_id, "INFO", end_msg, video_path)
            
    except Exception as e:
        error_msg = f"❌ FFmpeg Error: {e}"
        log_callback(error_msg)
        if session_id:
            log_to_database(session_id, "ERROR", error_msg, video_path)
    finally:
        final_msg = "⏹️ Streaming session ended"
        log_callback(final_msg)
        if session_id:
            log_to_database(session_id, "INFO", final_msg, video_path)

def get_youtube_categories():
    """Get YouTube video categories"""
    return {
        "1": "Film & Animation",
        "2": "Autos & Vehicles", 
        "10": "Music",
        "15": "Pets & Animals",
        "17": "Sports",
        "19": "Travel & Events",
        "20": "Gaming",
        "22": "People & Blogs",
        "23": "Comedy",
        "24": "Entertainment",
        "25": "News & Politics",
        "26": "Howto & Style",
        "27": "Education",
        "28": "Science & Technology"
    }

# Fungsi untuk auto start streaming
def auto_start_streaming(video_path, stream_key, is_shorts=False, custom_rtmp=None, session_id=None, duration_limit=None):
    """Auto start streaming dengan konfigurasi default"""
    if not video_path or not stream_key:
        st.error("❌ Video atau stream key tidak ditemukan!")
        return False
    
    # Set session state untuk streaming
    st.session_state['streaming'] = True
    st.session_state['stream_start_time'] = datetime.now()
    st.session_state['live_logs'] = []
    
    def log_callback(msg):
        if 'live_logs' not in st.session_state:
            st.session_state['live_logs'] = []
        st.session_state['live_logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        # Keep only last 100 logs in memory
        if len(st.session_state['live_logs']) > 100:
            st.session_state['live_logs'] = st.session_state['live_logs'][-100:]
    
    # Jalankan FFmpeg di thread terpisah
    st.session_state['ffmpeg_thread'] = threading.Thread(
        target=run_ffmpeg, 
        args=(video_path, stream_key, is_shorts, log_callback, custom_rtmp or None, session_id, duration_limit), 
        daemon=True
    )
    st.session_state['ffmpeg_thread'].start()
    
    # Log ke database
    log_to_database(session_id, "INFO", f"Auto streaming started: {video_path}")
    return True

# Fungsi untuk auto create live broadcast dengan setting manual/otomatis
def auto_create_live_broadcast(service, use_custom_settings=True, custom_settings=None, session_id=None):
    """Auto create live broadcast dengan setting manual atau otomatis"""
    try:
        with st.spinner("Creating auto YouTube Live broadcast..."):
            # Schedule for immediate start
            scheduled_time = datetime.now() + timedelta(seconds=30)
            
            # Default settings
            default_settings = {
                'title': f"Auto Live Stream {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                'description': "Auto-generated live stream",
                'tags': [],
                'category_id': "20",  # Gaming
                'privacy_status': "public",
                'made_for_kids': False
            }
            
            # Gunakan setting custom jika tersedia
            if use_custom_settings and custom_settings:
                settings = {**default_settings, **custom_settings}
            else:
                settings = default_settings
            
            live_info = create_live_stream(
                service, 
                settings['title'],
                settings['description'],
                scheduled_time,
                settings['tags'],
                settings['category_id'],
                settings['privacy_status'],
                settings['made_for_kids']
            )
            
            if live_info:
                st.session_state['current_stream_key'] = live_info['stream_key']
                st.session_state['live_broadcast_info'] = live_info
                st.success("🎉 Auto YouTube Live Broadcast Created Successfully!")
                log_to_database(session_id, "INFO", f"Auto YouTube Live created: {live_info['watch_url']}")
                return live_info
            else:
                st.error("❌ Failed to create auto live broadcast")
                return None
    except Exception as e:
        error_msg = f"Error creating auto YouTube Live: {e}"
        st.error(error_msg)
        log_to_database(session_id, "ERROR", error_msg)
        return None

def show_oauth_iframe():
    """Show OAuth iframe for authentication"""
    st.subheader("🔐 YouTube Authentication")
    
    if 'oauth_config' not in st.session_state:
        st.session_state['oauth_config'] = PREDEFINED_OAUTH_CONFIG['web']
    
    oauth_config = st.session_state['oauth_config']
    auth_url = generate_auth_url(oauth_config)
    
    if auth_url:
        st.markdown("### 🔐 Authenticate with YouTube")
        st.markdown("Click the button below to authenticate with your YouTube account:")
        
        # Create a button that opens OAuth in iframe
        if st.button("🔑 Authenticate with YouTube", type="primary"):
            st.session_state['show_oauth_iframe'] = True
            st.rerun()
        
        if st.session_state.get('show_oauth_iframe', False):
            st.markdown("### 🌐 Authentication Window")
            st.info("Please complete the authentication in the window below:")
            
            # Create iframe HTML
            iframe_html = f"""
            <iframe src="{auth_url}" 
                    width="100%" 
                    height="600" 
                    style="border: 1px solid #ccc; border-radius: 8px;">
                <p>Your browser does not support iframes. Please 
                <a href="{auth_url}" target="_blank">click here</a> to authenticate manually.</p>
            </iframe>
            """
            
            st.components.v1.html(iframe_html, height=600)
            
            st.markdown("---")
            st.markdown("### 🔑 Manual Code Entry")
            st.markdown("If you already have an authorization code, enter it below:")
            
            auth_code = st.text_input("Authorization Code", type="password", 
                                    placeholder="Paste authorization code here...")
            
            if st.button("🔄 Exchange Code for Tokens"):
                if auth_code:
                    with st.spinner("Exchanging code for tokens..."):
                        tokens = exchange_code_for_tokens(oauth_config, auth_code)
                        if tokens:
                            st.success("✅ Tokens obtained successfully!")
                            st.session_state['youtube_tokens'] = tokens
                            
                            # Create credentials for YouTube service
                            creds_dict = {
                                'access_token': tokens['access_token'],
                                'refresh_token': tokens.get('refresh_token'),
                                'token_uri': oauth_config['token_uri'],
                                'client_id': oauth_config['client_id'],
                                'client_secret': oauth_config['client_secret']
                            }
                            
                            # Test the connection
                            service = create_youtube_service(creds_dict)
                            if service:
                                channels = get_channel_info(service)
                                if channels:
                                    channel = channels[0]
                                    st.success(f"🎉 Connected to: {channel['snippet']['title']}")
                                    st.session_state['youtube_service'] = service
                                    st.session_state['channel_info'] = channel
                                    
                                    # Save channel authentication persistently
                                    save_channel_auth(
                                        channel['snippet']['title'],
                                        channel['id'],
                                        creds_dict
                                    )
                                    
                                    # Hide iframe after successful auth
                                    st.session_state['show_oauth_iframe'] = False
                                    st.rerun()
                                else:
                                    st.error("❌ Could not fetch channel information")
                            else:
                                st.error("❌ Failed to create YouTube service")
                        else:
                            st.error("❌ Failed to exchange code for tokens")
                else:
                    st.error("Please enter the authorization code")
            
            if st.button("❌ Close Authentication Window"):
                st.session_state['show_oauth_iframe'] = False
                st.rerun()

def main():
    # Page configuration must be the first Streamlit command
    st.set_page_config(
        page_title="Advanced YouTube Live Streaming",
        page_icon="📺",
        layout="wide"
    )
    
    # Initialize database
    init_database()
    
    # Initialize session state
    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if 'live_logs' not in st.session_state:
        st.session_state['live_logs'] = []
    
    st.title("🎥 Advanced YouTube Live Streaming Platform")
    st.markdown("---")
    
    # Check if we have URL parameters (for OAuth callback)
    query_params = st.experimental_get_query_params()
    
    # Handle OAuth callback if present
    if 'code' in query_params:
        auth_code = query_params['code'][0]
        st.info("🔄 Processing OAuth callback...")
        
        if 'oauth_config' in st.session_state:
            with st.spinner("Exchanging authorization code for tokens..."):
                tokens = exchange_code_for_tokens(st.session_state['oauth_config'], auth_code)
                if tokens:
                    st.session_state['youtube_tokens'] = tokens
                    
                    # Create credentials for YouTube service
                    oauth_config = st.session_state['oauth_config']
                    creds_dict = {
                        'access_token': tokens['access_token'],
                        'refresh_token': tokens.get('refresh_token'),
                        'token_uri': oauth_config['token_uri'],
                        'client_id': oauth_config['client_id'],
                        'client_secret': oauth_config['client_secret']
                    }
                    
                    # Test the connection
                    service = create_youtube_service(creds_dict)
                    if service:
                        channels = get_channel_info(service)
                        if channels:
                            channel = channels[0]
                            st.session_state['youtube_service'] = service
                            st.session_state['channel_info'] = channel
                            
                            # Save channel authentication persistently
                            save_channel_auth(
                                channel['snippet']['title'],
                                channel['id'],
                                creds_dict
                            )
                            
                            st.success(f"✅ Successfully connected to: {channel['snippet']['title']}")
                            
                            # Clear URL parameters
                            st.experimental_set_query_params()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to fetch channel information")
                    else:
                        st.error("❌ Failed to create YouTube service")
                else:
                    st.error("❌ Failed to exchange code for tokens")
        else:
            st.error("❌ OAuth configuration not found")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("📋 Configuration")
        
        # Session info
        st.info(f"🆔 Session: {st.session_state['session_id']}")
        
        # Saved Channels Section
        st.subheader("💾 Saved Channels")
        saved_channels = load_saved_channels()
        
        if saved_channels:
            st.write("**Previously authenticated channels:**")
            for channel in saved_channels:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📺 {channel['name']}")
                    st.caption(f"Last used: {channel['last_used'][:10]}")
                
                with col2:
                    if st.button("🔑 Use", key=f"use_{channel['name']}"):
                        # Load this channel's authentication
                        service = create_youtube_service(channel['auth'])
                        if service:
                            # Verify the authentication is still valid
                            channels = get_channel_info(service)
                            if channels:
                                channel_info = channels[0]
                                st.session_state['youtube_service'] = service
                                st.session_state['channel_info'] = channel_info
                                update_channel_last_used(channel['name'])
                                st.success(f"✅ Loaded: {channel['name']}")
                                st.rerun()
                            else:
                                st.error("❌ Authentication expired")
                        else:
                            st.error("❌ Failed to load authentication")
        else:
            st.info("No saved channels. Authenticate below to save.")
        
        # Google OAuth Configuration
        st.subheader("🔐 Google OAuth Setup")
        
        # Predefined Auth Button
        st.markdown("### 🚀 Quick Auth (Predefined)")
        if st.button("🔑 Use Predefined OAuth Config", help="Use built-in OAuth configuration"):
            st.session_state['oauth_config'] = PREDEFINED_OAUTH_CONFIG['web']
            st.success("✅ Predefined OAuth config loaded!")
            st.rerun()
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Check if user is authenticated
        if 'youtube_service' not in st.session_state:
            # Show OAuth iframe authentication
            show_oauth_iframe()
        else:
            # User is authenticated, show main interface
            st.header("🎥 Video & Streaming Setup")
            
            # Video selection
            video_files = [f for f in os.listdir('.') if f.endswith(('.mp4', '.flv', '.avi', '.mov', '.mkv'))]
            
            if video_files:
                st.write("📁 Available videos:")
                selected_video = st.selectbox("Select video", video_files)
            else:
                selected_video = None
                st.info("No video files found in current directory")
            
            # Video upload
            uploaded_file = st.file_uploader("Or upload new video", type=['mp4', '.flv', '.avi', '.mov', '.mkv'])
            
            if uploaded_file:
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.read())
                st.success("✅ Video uploaded successfully!")
                video_path = uploaded_file.name
                log_to_database(st.session_state['session_id'], "INFO", f"Video uploaded: {uploaded_file.name}")
            elif selected_video:
                video_path = selected_video
            else:
                video_path = None
            
            # YouTube Channel Info
            st.subheader("📺 YouTube Channel")
            channel = st.session_state['channel_info']
            col_ch1, col_ch2 = st.columns(2)
            
            with col_ch1:
                st.write(f"**Channel:** {channel['snippet']['title']}")
                st.write(f"**Subscribers:** {channel['statistics'].get('subscriberCount', 'Hidden')}")
            
            with col_ch2:
                st.write(f"**Views:** {channel['statistics'].get('viewCount', '0')}")
                st.write(f"**Videos:** {channel['statistics'].get('videoCount', '0')}")
            
            # YouTube Live Stream Management
            st.subheader("🎬 YouTube Live Stream Management")
            
            # Auto Live Stream Settings Mode
            st.markdown("### 🚀 Auto Live Stream Options")
            
            # Pilihan mode setting
            setting_mode = st.radio(
                "Mode Setting:", 
                ["🔧 Manual Settings", "⚡ Auto Settings"],
                horizontal=True
            )
            
            # Container untuk setting manual
            if setting_mode == "🔧 Manual Settings":
                with st.expander("📝 Manual Live Stream Settings", expanded=True):
                    # Basic settings
                    col_set1, col_set2 = st.columns(2)
                    
                    with col_set1:
                        auto_stream_title = st.text_input("🎬 Stream Title", value=f"Auto Live Stream {datetime.now().strftime('%Y-%m-%d %H:%M')}", key="auto_stream_title")
                        auto_privacy_status = st.selectbox("🔒 Privacy", ["public", "unlisted", "private"], key="auto_privacy_status")
                        auto_made_for_kids = st.checkbox("👶 Made for Kids", key="auto_made_for_kids")
                    
                    with col_set2:
                        categories = get_youtube_categories()
                        category_names = list(categories.values())
                        selected_category_name = st.selectbox("📂 Category", category_names, index=category_names.index("Gaming"), key="auto_category")
                        auto_category_id = [k for k, v in categories.items() if v == selected_category_name][0]
                        
                        auto_schedule_type = st.selectbox("⏰ Schedule", ["📍 Simpan sebagai Draft", "🔴 Publish Sekarang"], key="auto_schedule")
                    
                    # Description
                    auto_stream_description = st.text_area("📄 Stream Description", 
                                                         value="Auto-generated live stream with manual settings", 
                                                         max_chars=5000,
                                                         height=100,
                                                         key="auto_stream_description")
                    
                    # Tags
                    auto_tags_input = st.text_input("🏷️ Tags (comma separated)", 
                                                  placeholder="gaming, live, stream, youtube",
                                                  key="auto_tags_input")
                    auto_tags = [tag.strip() for tag in auto_tags_input.split(",") if tag.strip()] if auto_tags_input else []
                    
                    if auto_tags:
                        st.write("**Tags:**", ", ".join(auto_tags))
                    
                    # Simpan setting manual ke session state
                    st.session_state['manual_settings'] = {
                        'title': auto_stream_title,
                        'description': auto_stream_description,
                        'tags': auto_tags,
                        'category_id': auto_category_id,
                        'privacy_status': auto_privacy_status,
                        'made_for_kids': auto_made_for_kids
                    }
            
            # Auto Live Stream Button
            if st.button("🚀 Auto Start Live Stream", type="primary", help="Auto create and start live stream with selected settings"):
                service = st.session_state['youtube_service']
                
                # Tentukan setting yang akan digunakan
                if setting_mode == "🔧 Manual Settings" and 'manual_settings' in st.session_state:
                    use_custom_settings = True
                    custom_settings = st.session_state['manual_settings']
                    st.info("🔧 Using manual settings for live stream")
                else:
                    use_custom_settings = False
                    custom_settings = None
                    st.info("⚡ Using auto settings for live stream")
                
                # Auto create live broadcast dengan setting yang dipilih
                live_info = auto_create_live_broadcast(
                    service, 
                    use_custom_settings=use_custom_settings,
                    custom_settings=custom_settings,
                    session_id=st.session_state['session_id']
                )
                
                if live_info and video_path:
                    # Auto start streaming
                    if auto_start_streaming(
                        video_path, 
                        live_info['stream_key'],
                        session_id=st.session_state['session_id']
                    ):
                        st.success("🎉 Auto live stream started successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to start auto live stream")
                else:
                    st.error("❌ Need both YouTube service and video file to auto start")
            
            # Instructions panel
            with st.expander("💡 How to Use YouTube Live Features"):
                st.markdown("""
                **🔑 Get Stream Key Only:**
                - Creates a stream key without YouTube Live broadcast
                - Use with external streaming software (OBS, etc.)
                - Stream won't appear in YouTube Studio dashboard
                
                **🎬 Create YouTube Live:** ⭐ **RECOMMENDED**
                - Creates complete YouTube Live broadcast
                - Appears in YouTube Studio dashboard
                - Uses all settings from form below
                - Ready for audience immediately
                
                **🚀 Auto Start Live Stream:** ⭐ **AUTO MODE**
                - Automatically creates live broadcast
                - Starts streaming immediately
                - Choose between Manual or Auto settings
                
                **📋 View Existing Streams:**
                - Shows all your existing live broadcasts
                - Can reuse existing streams
                - Quick access to Watch and Studio URLs
                
                **⚠️ Important Notes:**
                - Select video file first
                - Choose setting mode (Manual/Auto)
                - YouTube Live broadcasts start in 30 seconds
                """)
            
            # Three main buttons
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("🔑 Get Stream Key Only", help="Get stream key without creating YouTube Live broadcast"):
                    try:
                        service = st.session_state['youtube_service']
                        with st.spinner("Getting stream key..."):
                            stream_info = get_stream_key_only(service)
                            if stream_info:
                                stream_key = stream_info['stream_key']
                                st.session_state['current_stream_key'] = stream_key
                                st.session_state['current_stream_info'] = stream_info
                                st.success("✅ Stream key obtained!")
                                log_to_database(st.session_state['session_id'], "INFO", "Stream key generated successfully")
                                
                                # Display stream information
                                st.info("🔑 **Stream Key Generated** (for external streaming software)")
                                col_sk1, col_sk2 = st.columns(2)
                                with col_sk1:
                                    st.text_input("Stream Key", value=stream_key, type="password", key="stream_key_display")
                                with col_sk2:
                                    st.text_input("RTMP URL", value=stream_info['stream_url'], key="rtmp_url_display")
                    except Exception as e:
                        error_msg = f"Error getting stream key: {e}"
                        st.error(error_msg)
                        log_to_database(st.session_state['session_id'], "ERROR", error_msg)
            
            with col_btn2:
                if st.button("🎬 Create YouTube Live", type="primary", help="Create complete YouTube Live broadcast (appears in Studio)"):
                    # Get form values
                    stream_title = st.session_state.get('stream_title_input', 'Live Stream')
                    stream_description = st.session_state.get('stream_description_input', 'Live streaming session')
                    tags_input = st.session_state.get('tags_input', '')
                    tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()] if tags_input else []
                    category_id = st.session_state.get('category_id', "20")
                    privacy_status = st.session_state.get('privacy_status', "public")
                    made_for_kids = st.session_state.get('made_for_kids', False)
                    
                    try:
                        service = st.session_state['youtube_service']
                        with st.spinner("Creating YouTube Live broadcast..."):
                            # Schedule for 30 seconds from now
                            scheduled_time = datetime.now() + timedelta(seconds=30)
                            
                            live_info = create_live_stream(
                                service, 
                                stream_title, 
                                stream_description, 
                                scheduled_time,
                                tags,
                                category_id,
                                privacy_status,
                                made_for_kids
                            )
                            
                            if live_info:
                                st.success("🎉 **YouTube Live Broadcast Created Successfully!**")
                                st.session_state['current_stream_key'] = live_info['stream_key']
                                st.session_state['live_broadcast_info'] = live_info
                                
                                # Display comprehensive information
                                st.info("📺 **Live Broadcast Information:**")
                                
                                col_info1, col_info2 = st.columns(2)
                                with col_info1:
                                    st.write(f"**🎬 Title:** {stream_title}")
                                    st.write(f"**🔒 Privacy:** {privacy_status.title()}")
                                    st.write(f"**📂 Category:** {get_youtube_categories().get(category_id, 'Unknown')}")
                                
                                with col_info2:
                                    st.write(f"**🏷️ Tags:** {', '.join(tags) if tags else 'None'}")
                                    st.write(f"**👶 Made for Kids:** {'Yes' if made_for_kids else 'No'}")
                                    st.write(f"**⏰ Scheduled:** {scheduled_time.strftime('%H:%M:%S')}")
                                
                                # Important links
                                st.markdown("### 🔗 Important Links:")
                                col_link1, col_link2 = st.columns(2)
                                
                                with col_link1:
                                    st.markdown(f"**📺 Watch URL:** [Open Stream]({live_info['watch_url']})")
                                    st.markdown(f"**🎛️ Studio URL:** [Manage in Studio]({live_info['studio_url']})")
                                
                                with col_link2:
                                    st.text_input("🔑 Stream Key", value=live_info['stream_key'], type="password", key="created_stream_key")
                                    st.text_input("🌐 RTMP URL", value=live_info['stream_url'], key="created_rtmp_url")
                                
                                st.success("✅ **Ready to stream!** Use the stream key above or click 'Start Streaming' below.")
                                
                                log_to_database(st.session_state['session_id'], "INFO", f"YouTube Live created: {live_info['watch_url']}")
                    except Exception as e:
                        error_msg = f"Error creating YouTube Live: {e}"
                        st.error(error_msg)
                        log_to_database(st.session_state['session_id'], "ERROR", error_msg)
            
            with col_btn3:
                if st.button("📋 View Existing Streams", help="View and manage existing live broadcasts"):
                    try:
                        service = st.session_state['youtube_service']
                        with st.spinner("Loading existing broadcasts..."):
                            broadcasts = get_existing_broadcasts(service)
                            
                            if broadcasts:
                                st.success(f"📺 Found {len(broadcasts)} existing broadcasts:")
                                
                                for i, broadcast in enumerate(broadcasts):
                                    with st.expander(f"🎬 {broadcast['snippet']['title']} - {broadcast['status']['lifeCycleStatus']}"):
                                        col_bc1, col_bc2 = st.columns(2)
                                        
                                        with col_bc1:
                                            st.write(f"**Title:** {broadcast['snippet']['title']}")
                                            st.write(f"**Status:** {broadcast['status']['lifeCycleStatus']}")
                                            st.write(f"**Privacy:** {broadcast['status']['privacyStatus']}")
                                            st.write(f"**Created:** {broadcast['snippet']['publishedAt'][:10]}")
                                        
                                        with col_bc2:
                                            watch_url = f"https://www.youtube.com/watch?v={broadcast['id']}"
                                            studio_url = f"https://studio.youtube.com/video/{broadcast['id']}/livestreaming"
                                            
                                            st.markdown(f"**Watch:** [Open]({watch_url})")
                                            st.markdown(f"**Studio:** [Manage]({studio_url})")
                                            
                                            if st.button(f"🔑 Use This Stream", key=f"use_broadcast_{i}"):
                                                # Get stream key for this broadcast
                                                stream_info = get_broadcast_stream_key(service, broadcast['id'])
                                                if stream_info:
                                                    st.session_state['current_stream_key'] = stream_info['stream_key']
                                                    st.session_state['live_broadcast_info'] = {
                                                        'broadcast_id': broadcast['id'],
                                                        'watch_url': watch_url,
                                                        'studio_url': studio_url,
                                                        'stream_key': stream_info['stream_key'],
                                                        'stream_url': stream_info['stream_url']
                                                    }
                                                    st.success(f"✅ Using stream: {broadcast['snippet']['title']}")
                                                    st.rerun()
                                                else:
                                                    st.error("❌ Could not get stream key for this broadcast")
                            else:
                                st.info("📺 No existing broadcasts found. Create a new one above!")
                    except Exception as e:
                        error_msg = f"Error loading existing broadcasts: {e}"
                        st.error(error_msg)
                        log_to_database(st.session_state['session_id'], "ERROR", error_msg)
    
    with col2:
        st.header("📊 Status & Controls")
        
        # Check if user is authenticated
        if 'youtube_service' in st.session_state:
            # Streaming status
            streaming = st.session_state.get('streaming', False)
            if streaming:
                st.error("🔴 LIVE")
                
                # Live stats
                if 'stream_start_time' in st.session_state:
                    duration = datetime.now() - st.session_state['stream_start_time']
                    st.metric("⏱️ Duration", str(duration).split('.')[0])
            else:
                st.success("⚫ OFFLINE")
            
            # Control buttons
            if st.button("▶️ Start Streaming", type="primary"):
                # Get the current stream key
                stream_key = st.session_state.get('current_stream_key', '')
                
                if not video_path:
                    st.error("❌ Please select or upload a video!")
                elif not stream_key:
                    st.error("❌ Stream key is required!")
                else:
                    # Save streaming session
                    save_streaming_session(
                        st.session_state['session_id'],
                        video_path,
                        stream_title,
                        stream_description,
                        ", ".join(tags),
                        category_id,
                        privacy_status,
                        made_for_kids,
                        st.session_state.get('channel_info', {}).get('snippet', {}).get('title', 'Unknown')
                    )
                    
                    # Start streaming
                    st.session_state['streaming'] = True
                    st.session_state['stream_start_time'] = datetime.now()
                    st.session_state['live_logs'] = []
                    
                    def log_callback(msg):
                        if 'live_logs' not in st.session_state:
                            st.session_state['live_logs'] = []
                        st.session_state['live_logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
                        # Keep only last 100 logs in memory
                        if len(st.session_state['live_logs']) > 100:
                            st.session_state['live_logs'] = st.session_state['live_logs'][-100:]
                    
                    # Ambil durasi dari pilihan pengguna
                    duration_limit = None
                    if duration_option == "⏱️ Custom Waktu":
                        duration_limit = total_custom_seconds
                    elif duration_option == "🎬 Ikuti Panjang Video":
                        video_duration = get_video_duration(video_path)
                        if video_duration:
                            duration_limit = int(video_duration)
                        else:
                            st.warning("Durasi video tidak ditemukan, streaming akan berjalan tanpa batas waktu.")
                    
                    st.session_state['ffmpeg_thread'] = threading.Thread(
                        target=run_ffmpeg, 
                        args=(video_path, stream_key, is_shorts, log_callback, custom_rtmp or None, st.session_state['session_id'], duration_limit), 
                        daemon=True
                    )
                    st.session_state['ffmpeg_thread'].start()
                    st.success("🚀 Streaming started!")
                    log_to_database(st.session_state['session_id'], "INFO", f"Streaming started: {video_path}")
                    st.rerun()
            
            if st.button("⏹️ Stop Streaming", type="secondary"):
                st.session_state['streaming'] = False
                if 'stream_start_time' in st.session_state:
                    del st.session_state['stream_start_time']
                os.system("pkill ffmpeg")
                if os.path.exists("temp_video.mp4"):
                    os.remove("temp_video.mp4")
                st.warning("⏸️ Streaming stopped!")
                log_to_database(st.session_state['session_id'], "INFO", "Streaming stopped by user")
                st.rerun()
            
            # Live broadcast info
            if 'live_broadcast_info' in st.session_state:
                st.subheader("📺 Live Broadcast")
                broadcast_info = st.session_state['live_broadcast_info']
                st.write(f"**Watch URL:** [Open Stream]({broadcast_info['watch_url']})")
                if 'studio_url' in broadcast_info:
                    st.write(f"**Studio URL:** [Manage]({broadcast_info['studio_url']})")
                st.write(f"**Broadcast ID:** {broadcast_info.get('broadcast_id', 'N/A')}")
            
            # Statistics
            st.subheader("📈 Statistics")
            
            # Session stats
            session_logs = get_logs_from_database(st.session_state['session_id'], 50)
            st.metric("Session Logs", len(session_logs))
            
            if 'live_logs' in st.session_state:
                st.metric("Live Log Entries", len(st.session_state['live_logs']))
            
            # Quick actions
            st.subheader("⚡ Quick Actions")
            
            if st.button("📋 Copy Stream Key"):
                if 'current_stream_key' in st.session_state:
                    st.code(st.session_state['current_stream_key'])
                    st.success("Stream key displayed above!")
            
            if st.button("🔄 Refresh Status"):
                st.rerun()
                
            # Durasi Streaming Otomatis
            st.subheader("🕒 Durasi Streaming Otomatis")

            duration_option = st.radio(
                "Pilih Durasi:",
                ("🔁 Loop Selamanya", "⏱️ Custom Waktu", "🎬 Ikuti Panjang Video"),
                index=0,
                key="duration_option"
            )

            if duration_option == "⏱️ Custom Waktu":
                custom_duration_hours = st.number_input("Jam", min_value=0, max_value=24, value=1, step=1)
                custom_duration_minutes = st.number_input("Menit", min_value=0, max_value=59, value=0, step=5)
                total_custom_seconds = custom_duration_hours * 3600 + custom_duration_minutes * 60
            elif duration_option == "🎬 Ikuti Panjang Video":
                st.info("Fitur ini membutuhkan deteksi durasi video menggunakan `ffprobe`. Pastikan sudah terinstal.")
            
            # Tampilkan estimasi durasi di UI
            if duration_option == "⏱️ Custom Waktu":
                st.info(f"⏰ Streaming akan berhenti otomatis setelah {timedelta(seconds=total_custom_seconds)}")
            elif duration_option == "🎬 Ikuti Panjang Video" and video_path:
                video_duration = get_video_duration(video_path)
                if video_duration:
                    st.info(f"⏰ Streaming akan berhenti otomatis setelah {timedelta(seconds=int(video_duration))}")
        else:
            st.info("🔐 Please authenticate with YouTube to access streaming controls.")
    
    # Live Logs Section (only show if authenticated)
    if 'youtube_service' in st.session_state:
        st.markdown("---")
        st.header("📝 Live Streaming Logs")
        
        # Log tabs
        tab1, tab2, tab3 = st.tabs(["🔴 Live Logs", "📊 Session History", "🗂️ All Logs"])
        
        with tab1:
            st.subheader("Real-time Streaming Logs")
            
            # Live logs container
            log_container = st.container()
            with log_container:
                if 'live_logs' in st.session_state and st.session_state['live_logs']:
                    # Show last 50 live logs
                    recent_logs = st.session_state['live_logs'][-50:]
                    logs_text = "\n".join(recent_logs)
                    st.text_area("Live Logs", logs_text, height=300, disabled=True, key="live_logs_display")
                else:
                    st.info("No live logs available. Start streaming to see real-time logs.")
            
            # Auto-refresh toggle
            auto_refresh = st.checkbox("🔄 Auto-refresh logs", value=streaming)
            
            if auto_refresh and streaming:
                time.sleep(2)
                st.rerun()
        
        with tab2:
            st.subheader("Current Session History")
            
            session_logs = get_logs_from_database(st.session_state['session_id'], 100)
            if session_logs:
                # Create a formatted display
                for log in session_logs[:20]:  # Show last 20 session logs
                    timestamp, log_type, message, video_file, channel_name = log
                    
                    # Color code by log type
                    if log_type == "ERROR":
                        st.error(f"**{timestamp}** - {message}")
                    elif log_type == "INFO":
                        st.info(f"**{timestamp}** - {message}")
                    elif log_type == "FFMPEG":
                        st.text(f"{timestamp} - {message}")
                    else:
                        st.write(f"**{timestamp}** - {message}")
            else:
                st.info("No session logs available yet.")
        
        with tab3:
            st.subheader("All Historical Logs")
            
            # Filter options
            col_filter1, col_filter2 = st.columns(2)
            
            with col_filter1:
                log_limit = st.selectbox("Show logs", [50, 100, 200, 500], index=1)
            
            with col_filter2:
                log_type_filter = st.selectbox("Filter by type", ["All", "INFO", "ERROR", "FFMPEG"])
            
            all_logs = get_logs_from_database(limit=log_limit)
            
            if all_logs:
                # Filter by type if selected
                if log_type_filter != "All":
                    all_logs = [log for log in all_logs if log[1] == log_type_filter]
                
                # Display in expandable sections
                for i, log in enumerate(all_logs[:50]):  # Limit display to 50 for performance
                    timestamp, log_type, message, video_file, channel_name = log
                    
                    with st.expander(f"{log_type} - {timestamp} - {message[:50]}..."):
                        st.write(f"**Timestamp:** {timestamp}")
                        st.write(f"**Type:** {log_type}")
                        st.write(f"**Message:** {message}")
                        if video_file:
                            st.write(f"**Video File:** {video_file}")
                        if channel_name:
                            st.write(f"**Channel:** {channel_name}")
            else:
                st.info("No historical logs available.")

if __name__ == '__main__':
    main()
