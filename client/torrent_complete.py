import os
import sys
import shutil
import subprocess
import requests
import redis
from requests.auth import HTTPDigestAuth
from requests.exceptions import ConnectionError
from requests.packages.urllib3.exceptions import ProtocolError
from twilio.rest import TwilioRestClient

"""
    You will need to install the following packages:
    twilio
    redis
    requests
"""

# FileBot stuff, you will need to install FileBot to name your files, if you don't want to install it
# Just set USE_FILEBOT to False
PATH_TO_FILEBOT_EXE = None  # "C:\Program Files\FileBot\\filebot.exe"
USE_FILBOT = False
# The path to your Plex folder where you want your movies moved into.
PATH_TO_PLEX_FOLDER = None  # "D:\Plex\Movies\"
# You need enabled qBitTorrent's Web UI and set a username and password
URL_FOR_TORRENT_CLIENT = None  # "http://127.0.0.1:80
TORRENT_USER_NAME = None  # "admin"
TORRENT_PASSWORD = None  # "admin"
# This will get the path from the torrent client.
PATH_TO_DOWNLOADS_FOLDER = sys.argv[1]
# Builds the name of the torrent from the sys.argv list
TORRENT_NAME = ""
for arg in sys.argv[2:]:
    TORRENT_NAME = TORRENT_NAME + arg + " "
TORRENT_NAME = TORRENT_NAME.strip()
# Twilio Integration to notify your user of movie completion.
# If you don't want to use Twilio set the USE_TWILIO flag to false
USE_TWILIO = False
TWILIO_ACCOUNT_SID = None
TWILIO_AUTH_TOKEN = None
TWILIO_PHONE_NUMBER = None
client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
# REDIS STUFF
REDIS_PW = None
REDIS_HOST = None
REDIS_PORT = None
r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PW,
                      decode_responses=True)

movie = ("", -1)


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


# Remove torrent from active torrents
post_response = requests.get(url=URL_FOR_TORRENT_CLIENT + "/json/torrents",
                             auth=HTTPDigestAuth(TORRENT_USER_NAME, TORRENT_PASSWORD))
active_torrents = post_response.json()
active_torrent = None
for torrent in active_torrents:
    if torrent['name'] == TORRENT_NAME:
        while True:
            try:
                post_response = requests.post(url=URL_FOR_TORRENT_CLIENT + "/command/delete",
                                              auth=HTTPDigestAuth(TORRENT_USER_NAME, TORRENT_PASSWORD),
                                              data={"hashes": torrent['hash']})
                active_torrent = torrent
                print(post_response.status_code)
                if post_response.status_code == 200:
                    repeat = False
            except ConnectionError as e:
                pass
            except ConnectionResetError as e:
                pass
            except ProtocolError as e:
                pass

search_for_largest_file(PATH_TO_DOWNLOADS_FOLDER + TORRENT_NAME)
if movie[1] != -1:
    download_directory_file_name = movie[0].rsplit("\\", 1)[1]
    download_directory_file_path = movie[0].rsplit("\\", 1)[0]
    path_to_file_in_plex_folder = PATH_TO_PLEX_FOLDER + download_directory_file_name

    shutil.move(movie[0], path_to_file_in_plex_folder)
    shutil.rmtree(download_directory_file_path)

    if USE_FILBOT:
        subprocess.call([PATH_TO_FILEBOT_EXE, "-rename", path_to_file_in_plex_folder], shell=True)

    if USE_TWILIO:
        redis_data = r.hgetall("torrent_hashes:" + active_torrent['hash'])
        message = "{} is ready for viewing.".format(redis_data['movie_title'])

        client.messages.create(to=redis_data['user'], from_=TWILIO_PHONE_NUMBER,
                               body=message)
