from telepot import Bot, glance
from telepot.namedtuple import InlineKeyboardMarkup
from os import environ
from twilio.rest import TwilioRestClient
from tpb import get_torrent_listings
import redis
import ast
import time
import requests
from requests.auth import HTTPDigestAuth

# Bot Initialize
bot = Bot(environ.get("TELEGRAM_BOT_TOKEN"))
# Redis
r = redis.StrictRedis(host=environ.get('REDIS_HOST'), port=environ.get('REDIS_PORT'), password=environ.get('REDIS_PW'),
                      decode_responses=True)
# Twilio
client = TwilioRestClient(environ.get("TWILIO_ACCOUNT_SID"), environ.get("TWILIO_AUTH_TOKEN"))


def on_chat_message(msg):
    pass


def on_callback_query(msg):
    query_id, from_id, data = glance(msg, flavor='callback_query')
    print('Callback query:', query_id, from_id, data)

    if data.startswith("torrents_"):
        request_id = data.split("_")[1]
        magnet_id_index = data.split("_")[2]
        request_data = r.hgetall("request:" + request_id)
        user = request_data['user']
        magnets = ast.literal_eval(request_data['magnet_links'])
        movie = ast.literal_eval(request_data['movie'])

        if magnet_id_index == "none":
            message = "There is no suitable download for {} ({}).".format(movie['title'], movie[
                'release_date'].split("-")[0])
            bot.editMessageText(
                msg_identifier=(int(environ.get("TELEGRAM_APPROVAL_CHAT_ID")), msg['message']['message_id']),
                text=message + "\nNotifying requester.")
            client.messages.create(to=user, from_=environ.get("TWILIO_PHONE_NUMBER"),
                                   body=message + " Request something else. Sorry.")
        else:
            post_response = requests.post(url=environ.get("TORRENT_CLIENT_URL") + "/command/download",
                                          data={'urls': magnets[int(magnet_id_index)][1]},
                                          auth=HTTPDigestAuth(environ.get("TORRENT_CLIENT_USERNAME"),
                                                              environ.get("TORRENT_CLIENT_PASSWORD")))
            if post_response.status_code == 200:
                message = "{} ({}) is now downloading for {}.".format(movie['title'],
                                                                      movie['release_date'].split("-")[0], user)
                bot.editMessageText(
                    msg_identifier=(int(environ.get("TELEGRAM_APPROVAL_CHAT_ID")), msg['message']['message_id']),
                    text=message)
                message = "{} ({}) is now downloading. You will be notified when it's ready to be viewed.".format(
                    movie['title'],
                    movie['release_date'].split("-")[0], user)
                client.messages.create(to=user, from_=environ.get("TWILIO_PHONE_NUMBER"),
                                       body=message)

                post_response = requests.get(url=environ.get("TORRENT_CLIENT_URL") + "/json/torrents",
                                             auth=HTTPDigestAuth(environ.get("TORRENT_CLIENT_USERNAME"),
                                                                 environ.get("TORRENT_CLIENT_PASSWORD")))
                active_torrents = post_response.json()
                for torrent in active_torrents:
                    if torrent['name'] == magnets[int(magnet_id_index)][0]:
                        hm = {"user": user,
                              "movie_title": "{} ({})".format(movie['title'], movie['release_date'].split("-")[0]),
                              "time_created": int(round(time.time())),
                              }
                        r.hmset("torrent_hashes:" + torrent['hash'], hm)
            else:
                message = "{} ({}) download could not be started for {}.".format(movie['title'],
                                                                                 movie['release_date'].split("-")[0],
                                                                                 user)
                bot.editMessageText(
                    msg_identifier=(int(environ.get("TELEGRAM_APPROVAL_CHAT_ID")), msg['message']['message_id']),
                    text=message)
    elif data.startswith("request_"):
        request_id = data.split("_")[1]
        boolean = data.split("_")[2]
        request_data = r.hgetall("request:" + request_id)
        user = request_data['user']
        movie = ast.literal_eval(request_data['movie'])
        request_message_id = request_data['approval_message_id']

        if boolean == 'true':
            message = "{} ({}) has been approved. You will be notified when it's starts downloading.".format(
                movie['title'],
                movie['release_date'].split("-")[0])
            client.messages.create(to=user, from_=environ.get("TWILIO_PHONE_NUMBER"), body=message)
            search_query = "{} {}".format(movie['title'], movie['release_date'].split("-")[0])
            category_int = 207
            torrents = get_torrent_listings(search_query, category_int)[0:4]

            # Checks to see if there was a results from the search, if not, create option to search again.
            # This is mostly because TPB is spotty and they sometimes are down.
            if len(torrents) == 0:
                message = "No suitable download options for {} ({}).".format(movie['title'],
                                                                             movie['release_date'].split("-")[0])
                buttons = [[dict(text="Search Again", callback_data="request_" + request_id + "_re")],
                           [dict(text="None of these", callback_data="request_" + request_id + "_none")]]
                markup = InlineKeyboardMarkup(inline_keyboard=buttons)
                telegram_response = bot.editMessageText(
                    msg_identifier=(int(environ.get("TELEGRAM_APPROVAL_CHAT_ID")), msg['message']['message_id']),
                    text=message,
                    reply_markup=markup)
                request_data['approval_message_id'] = telegram_response['message_id']
                r.hmset("request:{}".format(request_id), request_data)
                return
            else:
                # Send the approver a torrent picker.
                message = "Here are the torrent options for {} ({}).".format(movie['title'],
                                                                             movie['release_date'].split("-")[0])
                buttons = []
                for torrent in torrents:
                    buttons.append(
                        [dict(text=torrent['name'], callback_data="torrents_" + request_id + "_" + str(len(buttons)))])
                buttons.append([dict(text="None of these", callback_data="torrents_" + request_id + "_none")])
                markup = InlineKeyboardMarkup(inline_keyboard=buttons)
                telegram_response = bot.editMessageText(
                    msg_identifier=(environ.get("TELEGRAM_APPROVAL_CHAT_ID"), msg['message']['message_id']),
                    text=message,
                    reply_markup=markup)

                magnet_links = []
                for torrent in torrents:
                    magnet_links.append((torrent['name'], torrent['magnet']))
                r.hset("request:" + request_id, "torrent_selection_message_id", telegram_response['message_id'])
                r.hset("request:" + request_id, "magnet_links", str(magnet_links))
        elif boolean == 'false':
            message = "{} ({}) has been denied. It probably sucks anyway.".format(movie['title'],
                                                                                  movie['release_date'].split("-")[
                                                                                      0])
            client.messages.create(to=user, from_=environ.get("TWILIO_PHONE_NUMBER"), body=message)
            message = "{} ({}) has been denied for {}".format(movie['title'], movie['release_date'].split("-")[0], user)
            bot.editMessageText(
                msg_identifier=(int(environ.get("TELEGRAM_APPROVAL_CHAT_ID")), msg['message']['message_id']),
                text=message,
                reply_markup=None)
            pass
        elif boolean == 're':
            search_query = "{} {}".format(movie['title'], movie['release_date'].split("-")[0])
            category_int = 207
            torrents = get_torrent_listings(search_query, category_int)[0:4]

            # Checks to see if there was a results from the search, if not, create option to search again.
            # This is mostly because TPB is spotty and they sometimes are down.
            if len(torrents) == 0:
                response = requests.get('http://thepiratebay.org')
                tpb_status = None
                if response.status_code == 200:
                    tpb_status = "TPB is still up."
                else:
                    tpb_status = "TPB is down."

                message = "Still no suitable download options for {} ({}).\n\n<b>{}</b>".format(
                    movie['title'],
                    movie['release_date'].split("-")[0], tpb_status)
                buttons = []
                buttons.append([dict(text="Search Again", callback_data="request_" + request_id + "_re")])
                buttons.append([dict(text="None of these", callback_data="request_" + request_id + "_none")])
                markup = InlineKeyboardMarkup(inline_keyboard=buttons)
                bot.editMessageText(
                    msg_identifier=(int(environ.get("TELEGRAM_APPROVAL_CHAT_ID")), msg['message']['message_id']),
                    text=message, parse_mode="HTML", reply_markup=markup
                )
                r.hmset("request:{}".format(request_id), request_data)
                return
            else:
                # Send the approver a torrent picker.
                message = "Here are the torrent options for {} ({}).".format(movie['title'],
                                                                             movie['release_date'].split("-")[0])
                buttons = []
                for torrent in torrents:
                    buttons.append(
                        [dict(text=torrent['name'], callback_data="torrents_" + request_id + "_" + str(len(buttons)))])
                buttons.append([dict(text="None of these", callback_data="torrents_" + request_id + "_none")])
                markup = InlineKeyboardMarkup(inline_keyboard=buttons)
                bot.editMessageText(
                    msg_identifier=int(environ.get("TELEGRAM_APPROVAL_CHAT_ID"), msg['message']['message_id']),
                    text=message,
                    reply_markup=markup)

                magnet_links = []
                for torrent in torrents:
                    magnet_links.append((torrent['name'], torrent['magnet']))
                r.hset("request:" + request_id, "magnet_links", str(magnet_links))
        elif boolean == "none":
            message = "There is no suitable download for {} ({}).".format(movie['title'], movie[
                'release_date'].split("-")[0])
            bot.editMessageText(
                msg_identifier=(int(environ.get("TELEGRAM_APPROVAL_CHAT_ID")), msg['message']['message_id']),
                text=message + "\nNotifying requester.")
            client.messages.create(to=user, from_=environ.get("TWILIO_PHONE_NUMBER"),
                                   body=message + " Request something else. Sorry.")


bot.message_loop({'chat': on_chat_message, 'callback_query': on_callback_query})

# Keep the program running.
while 1:
    time.sleep(10)
