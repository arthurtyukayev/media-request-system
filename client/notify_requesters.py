from os import environ
from twilio.rest import TwilioRestClient
from redis import StrictRedis
from time import sleep

# Change this to false to actually send the message.
SAFETY = False

# Redis
REDIS_URL = environ.get('REDIS_URL')
REDIS_PW = REDIS_URL.rsplit(":", 1)[0].rsplit("@", 1)[0][10:]
REDIS_HOST = REDIS_URL.rsplit(":", 1)[0].rsplit("@", 1)[1]
REDIS_PORT = int(REDIS_URL.rsplit(":", 1)[1])
r = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PW,
                decode_responses=True)
# Twilio
client = TwilioRestClient(environ.get("TWILIO_ACCOUNT_SID"), environ.get("TWILIO_AUTH_TOKEN"))

# The message you want to send every user, if you would like to send more then one, then add a | between messages.
# I.E message = "this is one message.|this will send another message."
message = "THIS WILL SEND ONE SMS MESSAGE|and this will create a separate message."
# This will extract the messages into a list of messages.
messages = message.split("|")

# Gets all of the numbers from the database.
numbers = r.keys("users:*")

# This sets the delay you have to cancel the message before you're charged the money for the messages.
sleep_seconds = 5
print(
    "You're about to send {} SMS messages and it will cost you ${}\n You have {} seconds to cancel by closing this window.".format(
        len(messages) * len(numbers),
        (len(messages) * len(numbers)) * 0.0075, sleep_seconds)
)
sleep(sleep_seconds)

# Goes through the numbers and sends the messages.
for n in numbers:
    number = n.split(":")[1]
    for m in messages:
        if not SAFETY:
            client.messages.create(to=number, from_=environ.get('TWILIO_PHONE_NUMBER'), body=m)
        else:
            print("Sending \"{}\" to {}".format(m, number))
