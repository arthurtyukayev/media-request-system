from telepot import Bot, glance
from os import environ
from twilio.rest import TwilioRestClient
import redis
import ast

# Bot Initialize
bot = Bot(environ.get("TELEGRAM_BOT_TOKEN"))
# Redis
r = redis.StrictRedis(host=environ.get('REDIS_HOST'), port=environ.get('REDIS_PORT'), password=environ.get('REDIS_PW'),
                      decode_responses=True)
# Twilio
client = TwilioRestClient(environ.get("TWILIO_ACCOUNT_SID"), environ.get("TWILIO_AUTH_TOKEN"))


def on_callback_query(msg):
    query_id, from_id, data = glance(msg, flavor='callback_query')
    request_id = data.split("_")[0]
    action = data.split("_")[1]

    request_data = r.hgetall("request:" + request_id)
    user = request_data['user']
    movie = ast.literal_eval(request_data['requested_movie'])

    if action == 'true':
        message = "{} {} has been approved. It's downloading now.".format(movie['title'],
                                                                          movie['release_date'].split("-")[0])
        client.messages.create(to=user, from_=environ.get("TWILIO_PHONE_NUMBER"), body=message)
        # TODO: Download torrent
        # TODO: Notify user that movie is ready
        pass
    elif action == 'false':
        message = "{} {} has been denied. It was probably weird anyway.".format(movie['title'],
                                                                                movie['release_date'].split("-")[0])
        client.messages.create(to=user, from_=environ.get("TWILIO_PHONE_NUMBER"), body=message)
        pass


bot.message_loop({'callback_query': on_callback_query})
