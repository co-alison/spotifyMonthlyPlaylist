# spotifyMonthlyPlaylist

This is a Flask web app that generates a playlist of a user's saved tracks, top tracks, and recommendations based on the user's listening habits and followed artists' releases in a specified month and year/ The app uses the Spotify Web API to retrieve the user's data.

The app has the following features:
- Login with Spotify OAuth 2.0 to authorize access to the user's data.
- Input form for the user to specify the month and year for playlist generation.
- Playlist generation based on saved tracks, top tracks, releases from followed artists, and recommended tracks.
- A review page for users to remove tracks from the generated playlist and specify a custom title, description, and cover image.
- Error handling for Spotify API calls.

The app uses the following technologies:
- Flask, a Python web framework
- Spotipy, a Python library for the Spotify Web API
- HTML, CSS, and JavaScript for the front-end web interface

## Running the app locally

Make sure you have Python 3 and pip installed on your local machine and have a Spotify Developer account.
1. Clone the project repository from Github to your local machine.
2. Create a new virtual environment in the project directory using the following command:
    `$ python3 -m venv venv`
3. Active the virtual environment using the following command:
    `$ source venv/bin/activate`
4. Install the project dependencies using the following command:
    `$ pip install -r requirements.txt`
5. Go to the Spotify Developer Dashboard and create a new app.
6. Set the Redirect URI to: `http://localhost:3000/redirect`
7. Create a new file called `config.py` in the project directory and add the following code:
```
CLIENT_ID = 'your-client-id'
CLIENT_SECRET = 'your-client-secret'
SECRET_KEY = 'your-secret-key'
```
8. Replace `your-client-id`, `your-client-secret`, and `your-secret-key` with your own values. You can get your client ID and client secret from the Settings page of your new Spotify app.
9. Run the following command to start the Flask development server: `flask run`
10. Open http://localhost:3000 to access the web application.
