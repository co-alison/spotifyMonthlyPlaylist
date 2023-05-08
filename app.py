import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import random
import datetime
from config import CLIENT_ID, CLIENT_SECRET, SECRET_KEY

from flask import Flask, request, url_for, session, redirect, flash, render_template

import logging
logging.basicConfig(filename='myapp.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.secret_key = SECRET_KEY
TOKEN_INFO = 'token_info'

# home page
@app.route('/')
def index():
    token_info = get_token()
    if token_info:
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month

        years = [year for year in range(2008, current_year + 1)]
        months = [month for month in range(1, 13)]

        month_name = {
            1: 'January',
            2: 'February',
            3: 'March',
            4: 'April',
            5: 'May',
            6: 'June',
            7: 'July',
            8: 'August',
            9: 'September',
            10: 'October',
            11: 'November',
            12: 'December'
        }

        return render_template('create.html', years=years, months=months, current_year=current_year, current_month=current_month, month_name=month_name)
    else:
        return render_template('index.html')

@app.route('/login')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)

@app.route('/redirect')
def redirect_page():
    session.clear()
    # get authorization code
    code = request.args.get('code')
    # exchange code for access token
    try:
        token_info = create_spotify_oauth().get_access_token(code)
        session[TOKEN_INFO] = token_info
        return redirect('/')
    except spotipy.SpotifyException as e:
        flash('Error: {}'.format(e.msg))
        return redirect('/')
    
@app.route('/about')
def about():
    return ('about')

@app.route('/contact')
def contact():
    return ('contact')

@app.route('/privacy')
def privacy():
    return ('privacy')

@app.route('/monthlyPlaylist', methods=['POST'])
def get_monthly_playlist():
    try:
        token_info = get_token()
    except:
        logging.warning("User not logged in") 
        return redirect('/')
    
    year = request.form['year']
    month = request.form['month']
    
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # current user
    try:
        user = sp.current_user()
    except spotipy.SpotifyException as e:
        logging.error(f"An error occurred while retrieving user information: {e}")
        return 'An error occurred while retrieving your user information. Please try again later.'

    # get datetime object for the start of the year and month specified by the user
    selected_date = datetime.datetime(int(year), int(month), 1)

    # get user saved tracks in specified year and month
    try:
        saved_tracks = []
        results = sp.current_user_saved_tracks(limit=50)
        saved_tracks.extend(results['items'])
        while results['next']:
            results = sp.next(results)
            saved_tracks.extend(results['items'])
    except spotipy.SpotifyException as e:
        logging.error(f"An error occurred while retrieving saved tracks: {e}")
        return 'An error occurred while retrieving your saved tracks. Please try again later.'

    month_saved_tracks = []
    for item in saved_tracks:
        track = item['track']
        added_date = datetime.datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ')
        if added_date.year == selected_date.year and added_date.month == selected_date.month:
            month_saved_tracks.append(track)
            
    # get user top tracks only if specified year and month is last month
    current_year = datetime.datetime.now().year
    last_month = datetime.datetime.now().month - 1

    if current_year == selected_date.year and last_month == selected_date.month:
        try:
            top_tracks = sp.current_user_top_tracks(time_range="short_term")['items']
        except spotipy.SpotifyException as e:
            logging.error(f"An error occurred while retrieving top tracks: {e}")
            return 'An error occurred while retrieving your top tracks. Please try again later.'
    else:
        top_tracks = []

    # get user followed artists
    try:
        followed_artists = sp.current_user_followed_artists()
    except spotipy.SpotifyException as e:
        logging.error(f"An error occurred while retrieving followed artists: {e}")
        return 'An error occurred while retrieving your followed artists. Please try again later.'
    
    # get releases from followed artists in specified month/year
    month_releases = []
    for artist in followed_artists['artists']['items']:
        try:
            artist_top_tracks = sp.artist_top_tracks(artist['id'], user['country'])
        except spotipy.SpotifyException as e:
            logging.error(f"An error occurred while retrieving new releases: {e}")
            return 'An error occurred while retrieving new releases. Please try again later.'
        
        for track in artist_top_tracks['tracks']:
            track_date = datetime.datetime.strptime(track['album']['release_date'], '%Y-%m-%d')
            if track_date.year == selected_date.year and track_date.month == selected_date.month:
                month_releases.append(track)

    # generate seeds for recommendation
    seed_artist_ids = [artist['id'] for artist in followed_artists['artists']['items'][:5]]
    random.shuffle(seed_artist_ids)
    seed_artist_ids = seed_artist_ids[:2]

    seed_track_ids = [item['track']['id'] for item in saved_tracks[:5]]
    random.shuffle(seed_track_ids)
    seed_track_ids = seed_track_ids[:2]

    saved_track_features = sp.audio_features(seed_track_ids)
    saved_track_genres = set([genre for features in saved_track_features for genre in features.get('genres', [])])
    seed_genres = list(saved_track_genres)
    random.shuffle(seed_genres)
    seed_genres = seed_genres[:1]

    try:
        recommended_tracks = sp.recommendations(seed_artists=seed_artist_ids, seed_tracks=seed_track_ids, limit=10)['tracks'] if (seed_track_ids or seed_artist_ids or seed_genres) else []
    except spotipy.SpotifyException as e:
        logging.error(f"An error occurred while generating recommendations: {e}")
        return 'An error has occurred while generating your recommendations. Please try again later.'
    
    # combine all tracks and get unique tracks
    all_month_tracks = month_saved_tracks + top_tracks + month_releases + recommended_tracks
    random.shuffle(all_month_tracks)

    if len(all_month_tracks) < 10:
        return 'There is not enough data for the selected month/year combination. Please select a different one.'
    
    unique_track_ids = set(track['id'] for track in all_month_tracks)

    # get unique playlist name (in case of duplicate)
    playlist_name = selected_date.strftime('%B %Y')
    playlist_name_unique = playlist_name

    try:
        playlist_names = [p['name'] for p in sp.current_user_playlists()['items']]
    except spotipy.SpotifyException as e:
        logging.error(f"An error occurred: {e}")
        return 'An error has occurred. Please try again later.'

    i = 1
    while playlist_name_unique in playlist_names:
        playlist_name_unique = f"{playlist_name} ({i})"
        i += 1

    # go to review page
    # redirect(url_for('review', playlist_name=playlist_name_unique, user_id=user['id']))
    render_template('review.html', playlist_name=playlist_name_unique)

@app.route('/review')
def review():
    playlist_name = request.args.get('playlist_name')
    user_id = request.args.get('user_id')

    
    # # create playlist
    # try:
    #     monthly_playlist = sp.user_playlist_create(
    #         user_id, 
    #         name=playlist_name,
    #         public=False,
    #         collaborative=False, 
    #         description="Replay the month with a curated selection of your favourite songs, recent discoveries, plus new releases and recommended tracks based on your listening habits."
    #     )
    # except spotipy.SpotifyException as e:
    #     logging.error(f"An error occurred: {e}")
    #     return 'An error has occurred. Please try again later.'

    # # add tracks to new playlist
    # try:
    #     sp.playlist_add_items(monthly_playlist['id'], unique_track_ids)
    # except spotipy.SpotifyException as e:
    #     logging.error(f"An error occurred: {e}")
    #     return 'An error has occurred. Please try again later.'

    # return ("Monthly playlist created successfully")

def get_account_creation_date():
    try:
        token_info = get_token()
    except:
        logging.warning("User not logged in") 
        return redirect('/')
    
    sp = spotipy.Spotify(auth=token_info['access_token'])
    saved_tracks = sp.current_user_saved_tracks()
    saved_tracks_sorted = sorted(saved_tracks['items'], key=lambda x: x['added_at'])

    earliest_track = saved_tracks_sorted[0]['track']
    account_creation_date = earliest_track['album']['release_date']

    return datetime.datetime.strptime(account_creation_date, '%Y-%m-%d').date()

def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        logging.warning('TOKEN_INFO key is not found in session')
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