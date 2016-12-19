import os
import sys
import shutil
import subprocess
import requests
import redis
import configparser
from requests.auth import HTTPDigestAuth
from requests.exceptions import ConnectionError
from requests.packages.urllib3.exceptions import ProtocolError
from twilio.rest import TwilioRestClient

"""
    You will need to install the following runtime:
    Python 3.5

    You will need to install the following packages:
    twilio
    redis
    requests
"""

config = configparser.ConfigParser()
"""
    Find your torrent_complete_config.ini file, which should be in the same folder as this file.
    If you're on windows make sure you escape your path.
"""

# CHANGE THIS TO THE ACTUAL PATH TO THE INI CONFIG FILE.
config.read("PATH_TO_CONFIG_INI")

# Checks the config file for the path to the Filebot Installation
PATH_TO_FILEBOT_EXE = config['filebot'].get("PATH_TO_FILEBOT_EXE")
USE_FILBOT = config['filebot'].getboolean('USE_FILEBOT')
# Gets the path to your Movies Plex folder.
PATH_TO_PLEX_FOLDER = config['plex'].get("PATH_TO_PLEX_FOLDER")
# Gets the URL for qBitTorrent Web API.
URL_FOR_TORRENT_CLIENT = config['torrent'].get("URL_FOR_TORRENT_CLIENT")
# Username for qBitTorrent Web API.
TORRENT_USER_NAME = config['torrent'].get('TORRENT_USER_NAME')
# Password for qBitTorrent Web API.
TORRENT_PASSWORD = config['torrent'].get('TORRENT_PASSWORD')
# Gets the path to the downloads folder from the system arguments when calling the script from qBitTorrent.
PATH_TO_DOWNLOADS_FOLDER = sys.argv[1]
# Builds the torrent name from the system arguements.
TORRENT_NAME = ""
for arg in sys.argv[2:]:
    TORRENT_NAME = TORRENT_NAME + arg + " "
TORRENT_NAME = TORRENT_NAME.strip()
# Placeholder variable to be filled later.
TORRENT_HASH = None
# Gets the Twilio information from the config file.
USE_TWILIO = config['twilio'].getboolean('USE_TWILIO')
TWILIO_ACCOUNT_SID = config['twilio'].get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = config['twilio'].get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = config['twilio'].get("TWILIO_PHONE_NUMBER")
# Connects to the Twilio servers.
client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
# Gets the Redis information.
REDIS_URL = config['redis'].get("REDIS_URL")
REDIS_PW = REDIS_URL.rsplit(":", 1)[0].rsplit("@", 1)[0][10:]
REDIS_HOST = REDIS_URL.rsplit(":", 1)[0].rsplit("@", 1)[1]
REDIS_PORT = int(REDIS_URL.rsplit(":", 1)[1])
# Connects to Redis.
r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PW,
                      decode_responses=True)

movie = ("", -1)


# This function is used to find the largest file in a given path, nearly every time this will be the media requested.
# I guess this could cause the script to fail, however I've never seen a torrent that has a file larger then the movie
# itself.
def search_for_largest_file(d):
    global movie
    for item in os.listdir(d):
        item = d + "\\" + item
        if os.path.isdir(item):
            search_for_largest_file(item)
        else:
            itemsize = os.path.getsize(item)
            if itemsize > movie[1]:
                movie = (item, itemsize)


# Remove torrent from active torrents using the qBitTorrent Web API.
# Because the script is fired when the torrent finished, we need to remove it from qBitTorrent where is it left seeding.
# We need remove it so that we can do operations on the file and it's folder.
post_response = requests.get(url=URL_FOR_TORRENT_CLIENT + "/json/torrents",
                             auth=HTTPDigestAuth(TORRENT_USER_NAME, TORRENT_PASSWORD))
# JSON response of active torrents in qBitTorrent.
active_torrents = post_response.json()
active_torrent = None
# Loops through the active torrents matches the name of the active torrent to the name of the torrent passed through
# the system arguments.
for torrent in active_torrents:
    if torrent['name'] == TORRENT_NAME:
        while True:
            try:
                post_response = requests.post(url=URL_FOR_TORRENT_CLIENT + "/command/delete",
                                              auth=HTTPDigestAuth(TORRENT_USER_NAME, TORRENT_PASSWORD),
                                              data={"hashes": torrent['hash']})
                active_torrent = torrent
                if post_response.status_code == 200:
                    repeat = False

                    # Moves the torrent folder into it's own folder for searching
                    # This is required because some torrents don't nest their files into their own folders.
                    # For proper movement, all torrent files must be nested in a folder, this nests the files no matter
                    # what, just in case.
                    safe_path = PATH_TO_DOWNLOADS_FOLDER + "\\" + torrent['hash'] + "\\"
                    os.makedirs(safe_path)
                    shutil.move(PATH_TO_DOWNLOADS_FOLDER + "\\" + TORRENT_NAME, safe_path)
                    PATH_TO_DOWNLOADS_FOLDER = safe_path
                    TORRENT_HASH = torrent['hash']
                    break
            except ConnectionError as e:
                pass
            except ConnectionResetError as e:
                pass
            except ProtocolError as e:
                pass

# If the torrent isn't nested and is just a single file then this will check and provide the proper path to the
# search_for_largest_file()
if os.path.isfile(PATH_TO_DOWNLOADS_FOLDER + "\\" + TORRENT_NAME):
    search_for_largest_file(PATH_TO_DOWNLOADS_FOLDER)
else:
    search_for_largest_file(PATH_TO_DOWNLOADS_FOLDER + "\\" + TORRENT_NAME)

# This will check to make sure a file was found, usually there will always be a file, and it will be the largest file
# in the folder.
if movie[1] != -1:
    # Gets the name of the largest file in the folder.
    download_directory_file_name = movie[0].rsplit("\\", 1)[1]
    # download_directory_file_path = movie[0].rsplit("\\", 1)[0]
    path_to_file_in_plex_folder = PATH_TO_PLEX_FOLDER + download_directory_file_name

    shutil.move(movie[0], path_to_file_in_plex_folder)
    shutil.rmtree(PATH_TO_DOWNLOADS_FOLDER)

    # If Filebot is enabled in the config file this will use filebot to rename the torrent.
    if USE_FILBOT:
        subprocess.call([PATH_TO_FILEBOT_EXE, "-rename", path_to_file_in_plex_folder], shell=True)
    # If you have Twilio configured, this will send a text message to the requester notifying them that their file is ready for viewing.
    if USE_TWILIO:
        redis_data = r.hgetall("torrent_hashes:" + active_torrent['hash'])
        message = "{} is ready for viewing.".format(redis_data['movie_title'])

        client.messages.create(to=redis_data['user'], from_=TWILIO_PHONE_NUMBER,
                               body=message)
