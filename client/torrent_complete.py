import os
import sys
import shutil
import subprocess
import requests
from requests.auth import HTTPDigestAuth
from requests.exceptions import ConnectionError
from requests.packages.urllib3.exceptions import ProtocolError

PATH_TO_FILEBOT_EXE = None  # "C:\Program Files\FileBot\\filebot.exe"
USE_FILBOT = False

PATH_TO_PLEX_FOLDER = None  # "D:\Plex\Movies\"

URL_FOR_TORRENT_CLIENT = None  # "http://127.0.0.1:80
TORRENT_USER_NAME = None  # admin
TORRENT_PASSWORD = None  # admin

PATH_TO_DOWNLOADS_FOLDER = sys.argv[1]
# Builds the name of the torrent from the sys.argv list
TORRENT_NAME = ""
for arg in sys.argv[2:]:
    TORRENT_NAME = TORRENT_NAME + arg + " "
TORRENT_NAME = TORRENT_NAME.strip()

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
for torrent in active_torrents:
    if torrent['name'] == TORRENT_NAME:
        while True:
            try:
                post_response = requests.post(url=URL_FOR_TORRENT_CLIENT + "/command/delete",
                                              auth=HTTPDigestAuth(TORRENT_USER_NAME, TORRENT_PASSWORD),
                                              data={"hashes": torrent['hash']})
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
