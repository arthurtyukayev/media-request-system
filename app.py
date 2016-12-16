from flask import Flask, request
from os import environ
from twilio import twiml
from telepot.namedtuple import InlineKeyboardMarkup
from telepot import Bot
from telepot.exception import BadHTTPResponse
from uuid import uuid4
from plexapi.server import PlexServer
import tmdbsimple as tmdb
import redis
import time
import ast

app = Flask(__name__)

# TheMovieDB Initialize
tmdb.API_KEY = environ.get("TMDB_API_KEY")

# Telegram Bot API Initialize
bot = Bot(environ.get("TELEGRAM_BOT_TOKEN"))

# Redis
r = redis.StrictRedis(host=environ.get('REDIS_HOST'), port=environ.get('REDIS_PORT'), password=environ.get('REDIS_PW'),
                      decode_responses=True)

# Plex API
plex = PlexServer(environ.get("PLEX_URL"), environ.get("PLEX_AUTH_STRING"))


@app.route("/")
def hello():
    return "You're not allowed here."


@app.route("/incoming-sms", methods=['GET', 'POST'])
def incoming_sms():
    # Get the message the user sent our Twilio number
    body = request.values.get('Body', None)
    number = request.values.get('From', None)
    # Start our TwiML response
    resp = twiml.Response()

    # Parse the body to match for keywords
    if body.lower() == 'Yes'.lower():
        previous_request = r.hgetall("users:" + number)
        # Make sure the user has made a movie request before confirming.
        if previous_request is None:
            reply = "Please make a request before confirming. " \
                    "If you're searching for a movie called \"Yes\", then I'm sorry, I cannot find that movie."
            resp.message(reply)
            return str(resp)
        # Checks to see if the user has an expired movie request.
        if (int(time.time()) - int(previous_request['time_requested'])) > 30:
            reply = "You'r previous request has expired. Please make a new request."
            resp.message(reply)
            return str(resp)

        uuid_gen = str(uuid4())
        movie = ast.literal_eval(previous_request['requested_movie'])

        # Request Approval Bot Message
        buttons = [
            [dict(text='Approve', callback_data="request_" + uuid_gen + '_true')],
            [dict(text='Deny', callback_data="request_" + uuid_gen + '_false')]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = "<b>Movie Request</b>\n {} has requested the following movie.\n" \
               "\n<b>Title</b>: {}\n<b>Year</b> {}\n<b>Overview</b>: {}".format(
            number,
            movie['title'],
            movie['release_date'].split("-")[0],
            movie['overview'])
        try:
            telegram_response = bot.sendMessage(chat_id=environ.get('TELEGRAM_APPROVAL_CHAT_ID'), text=text,
                                                reply_markup=markup,
                                                parse_mode="HTML")
            r.hmset("request:{}".format(uuid_gen), {"movie": movie, "user": number, "time": int(time.time()),
                                                    "approval_message_id": telegram_response['message_id']})
        except BadHTTPResponse as e:
            pass

        reply = "Great! Your request is pending approval. P.S It has a better chance of being approved if you bribe Arthur."
        resp.message(reply)
        return str(resp)

    # Search TMDB for Movie
    search = tmdb.Search()
    search.movie(query=body)
    if len(search.results) == 0:
        reply = "No results found for that request. Be more specific. This only supports movies currently."
        resp.message(reply)
        return str(resp)
    else:
        request_movie = search.results[0]['title']

        plex_movies = plex.library.section('Movies')
        for movie in plex_movies.search():
            if movie == request_movie:
                # Reply that movie is already available.
                reply = "The movie {} ({}) is already available. Ignoring this request.".format(
                    request_movie, search.results[0]['release_date'].split("-")[0])
                resp.message(reply)
                return str(resp)

        r.hmset("users:" + number, {"requested_movie": search.results[0], "time_requested": int(time.time())})

        # Reply with the movie title
        reply = "You've requested {0} ({1}), if this is correct reply \"Yes\", otherwise please make a more specific request.".format(
            request_movie, search.results[0]['release_date'].split("-")[0])
        resp.message(reply)
        return str(resp)


if __name__ == "__main__":
    app.run(debug=False, host=environ.get("FLASK_HOST"), port=int(environ.get("PORT")))
