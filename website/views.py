import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import random
import datetime
import os
from werkzeug.utils import secure_filename
from PIL import Image
import base64
import logging
from flask import Blueprint, request, url_for, session, redirect, flash, render_template

from dotenv import dotenv_values
env_values = dotenv_values('.env')

CLIENT_ID = env_values['CLIENT_ID']
CLIENT_SECRET = env_values['CLIENT_SECRET']
UPLOAD_FOLDER = env_values['UPLOAD_FOLDER']
TOKEN_INFO = 'token_info'
MAX_IMAGE_SIZE = 256000
views = Blueprint('views', __name__)

# home page
@views.route('/')
def index():
    token_info = get_token()
    if token_info:
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month

        years = [year for year in range(2008, current_year + 1)]

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

        return render_template('generate.html', years=years, current_year=current_year, current_month=current_month, month_name=month_name)
    else:
        return render_template('index.html')

@views.route('/login')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)

@views.route('/redirect')
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
    
@views.route('/about')
def about():
    return render_template('about.html')

@views.route('/contact')
def contact():
    return render_template('contact.html')

@views.route('/privacy')
def privacy():
    return render_template('privacy.html')

@views.route('/monthlyPlaylist', methods=['POST'])
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
    
    unique_tracks = set(all_month_tracks)

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

    description = "Replay the month with a curated selection of your favourite songs, recent discoveries, plus new releases and recommended tracks based on your listening habits."

    return render_template('review.html', playlist_name=playlist_name_unique, description=description, tracks=unique_tracks)

@views.route('/monthlyPlaylist/create', methods=['POST'])
def create():
    title = request.form.get('title')
    description = request.form.get('description')
    cover_image = request.files.get('cover-image')
    selected_track_ids = request.form.get('selected_tracks')
    track_ids = request.form.getlist('tracks')

    try:
        token_info = get_token()
    except:
        logging.warning("User not logged in") 
        return redirect('/')

    track_ids_to_keep = []
    for track_id in track_ids:
        if track_id not in selected_track_ids:
            track_ids_to_keep.append(str(track_id))

    sp = spotipy.Spotify(auth=token_info['access_token'])

    # current user
    try:
        user = sp.current_user()
    except spotipy.SpotifyException as e:
        logging.error(f"An error occurred while retrieving user information: {e}")
        return 'An error occurred while retrieving your user information. Please try again later.'

    # create playlist
    try:
        monthly_playlist = sp.user_playlist_create(
            user['id'], 
            name=title,
            public=False,
            collaborative=False, 
            description=description
        )
    except spotipy.SpotifyException as e:
        logging.error(f"An error occurred: {e}")
        return 'An error has occurred. Please try again later.'
    
    # upload cover image
    if cover_image:
        filename = secure_filename(cover_image.filename)
        cover_image_path = os.path.join(UPLOAD_FOLDER, filename)
        cover_image.save(cover_image_path)

        # check image size and compress if necessary
        if os.path.getsize(cover_image_path) > MAX_IMAGE_SIZE:
            with Image.open(cover_image_path) as img:
                img.save(cover_image_path, optimize=True, quality=95)

        with open(cover_image_path, 'rb') as f:
            try:
                image_data = f.read()

                # encode image data as base64 encoded JPEG image string
                image_data_base64 = base64.b64encode(image_data).decode('utf-8')
                sp.playlist_upload_cover_image(monthly_playlist['id'], image_data_base64)
            except spotipy.SpotifyException as e:
                logging.error(f"An error occurred while uploading cover image: {e}")

        os.remove(cover_image_path)

    # add tracks to new playlist
    try:
        sp.playlist_add_items(monthly_playlist['id'], track_ids_to_keep)
    except spotipy.SpotifyException as e:
        logging.error(f"An error occurred: {e}")
        return 'An error has occurred. Please try again later.'

    return render_template('success.html')

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
        return None

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
        redirect_uri = url_for('views.redirect_page', _external = True),
        scope= 'user-library-read user-top-read user-follow-read playlist-modify-public playlist-modify-private user-read-private user-read-email ugc-image-upload'
        )