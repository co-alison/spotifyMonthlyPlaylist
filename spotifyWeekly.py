import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import random
import datetime
from config import CLIENT_ID, CLIENT_SECRET

from flask import Flask, request, url_for, session, redirect

app = Flask(__name__)

app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.secret_key = 'fje83J#W*@j3kljdfa8#3kjd*03'
TOKEN_INFO = 'token_info'

# handle logging in
@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)

@app.route('/redirect')
def redirect_page():
    session.clear()
    # get authorization code
    code = request.args.get('code')
    # exchange code for access token
    token_info = create_spotify_oauth().get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('get_monthly_playlist', _external = True))

@app.route('/monthlyPlaylist')
def get_monthly_playlist():
    try:
        token_info = get_token()
    except:
        print("User not logged in") 
        return redirect('/')
    
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # current user
    user = sp.current_user()

    # get date one month ago
    one_month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    
    # get user saved tracks in last month
    saved_tracks = sp.current_user_saved_tracks()
    last_month_saved_tracks = []
    for item in saved_tracks['items']:
        track = item['track']
        added_date = datetime.datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ')
        if added_date >= one_month_ago:
            last_month_saved_tracks.append(track)
            
    # get user top tracks in last month
    top_tracks = sp.current_user_top_tracks(time_range="short_term")['items']

    # get user followed artists
    followed_artists = sp.current_user_followed_artists()

    # get new releases from followed artists
    new_releases = []
    for artist in followed_artists['artists']['items']:
        artist_top_tracks = sp.artist_top_tracks(artist['id'], user['country'])
        for track in artist_top_tracks['tracks']:
            track_date = datetime.datetime.strptime(track['album']['release_date'], '%Y-%m-%d')
            if track_date >= one_month_ago:
                new_releases.append(track)

    # generate seeds for recommendation
    seed_artist_ids = [artist['id'] for artist in followed_artists['artists']['items'][:5]]
    random.shuffle(seed_artist_ids)
    seed_artist_ids = seed_artist_ids[:2]

    seed_track_ids = [item['track']['id'] for item in saved_tracks['items'][:5]]
    random.shuffle(seed_track_ids)
    seed_track_ids = seed_track_ids[:2]

    saved_track_features = sp.audio_features(seed_track_ids)
    saved_track_genres = set([genre for features in saved_track_features for genre in features.get('genres', [])])
    seed_genres = list(saved_track_genres)
    random.shuffle(seed_genres)
    seed_genres = seed_genres[:1]

    recommended_tracks = sp.recommendations(seed_artists=seed_artist_ids, seed_tracks=seed_track_ids, limit=10)['tracks'] if (seed_track_ids or seed_artist_ids or seed_genres) else []

    # combine all tracks and get unique tracks
    last_month_tracks = last_month_saved_tracks + top_tracks + new_releases + recommended_tracks
    unique_track_ids = set(track['id'] for track in last_month_tracks)
    
    # create playlist
    monthly_playlist = sp.user_playlist_create(
        user['id'], 
        name=datetime.datetime.now().strftime('%B %Y'),
        public=False,
        collaborative=False, 
        description="Replay the last month with a curated selection of your favourite songs, recent discoveries, plus new releases and recommended tracks based on your listening habits."
    )

    # add tracks to new playlist
    sp.playlist_add_items(monthly_playlist['id'], unique_track_ids)

    return ("Monthly playlist created successfully")


def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        redirect(url_for('login', _external = False))

    now = int(time.time())

    is_expired = token_info['expires_at'] - now < 60
    if (is_expired):
        spotify_oauth = create_spotify_oauth()
        token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id= CLIENT_ID,
        client_secret= CLIENT_SECRET,
        redirect_uri = url_for('redirect_page', _external = True),
        scope= 'user-library-read user-top-read user-follow-read playlist-modify-public playlist-modify-private user-read-private user-read-email'
        )

app.run(host="localhost", port=3000, debug=True)