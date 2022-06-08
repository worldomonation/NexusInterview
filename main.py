import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

import requests
import twitter

WEEK_DELTA = 12  # Weeks
LOCATIONS = [
    ("Blaine", 5020),
]

LOGGING_FORMAT = "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"

SCHEDULER_API_URL = "https://ttp.cbp.dhs.gov/schedulerapi/locations/{location}/slots?startTimestamp={start}&endTimestamp={end}"  # noqa
TTP_TIME_FORMAT = "%Y-%m-%dT%H:%M"

NOTIF_MESSAGE = "New appointment slot open at {location}: {date}"
MESSAGE_TIME_FORMAT = "%A, %B %d, %Y at %I:%M %p"


def tweet(message: str) -> None:

    api = twitter.Api(
        consumer_key=os.environ["CONSUMER_KEY"],
        consumer_secret=os.environ["CONSUMER_SECRET"],
        access_token_key=os.environ["ACCESS_TOKEN_KEY"],
        access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
    )
    try:
        api.PostUpdate(message)
    except twitter.TwitterError as e:
        if len(e.message) == 1 and e.message[0]["code"] == 187:
            logging.info("Tweet rejected (duplicate status)")
        else:
            raise


def check_for_openings(location_name: str, location_code: int, args: argparse) -> None:

    start = datetime.now()
    end = start + timedelta(weeks=WEEK_DELTA)

    url = SCHEDULER_API_URL.format(
        location=location_code,
        start=start.strftime(TTP_TIME_FORMAT),
        end=end.strftime(TTP_TIME_FORMAT)
    )
    logging.info(f"Fetching data from {url}")

    try:
        results = requests.get(url).json()
    except requests.ConnectionError:
        logging.exception("Could not connect to scheduler API")
        sys.exit(1)

    for result in results:
        if result["active"] > 0:
            logging.info(f"Opening found for {location_name}")

            timestamp = datetime.strptime(result["timestamp"], TTP_TIME_FORMAT)
            message = NOTIF_MESSAGE.format(
                location=location_name,
                date=timestamp.strftime(MESSAGE_TIME_FORMAT)
            )
            if args.test:
                print(message)
            if args.tweet:
                logging.info(f"Tweeting: {message}")
                tweet(message)
            else:
                os.system("""osascript -e 'display notification "{}" with title "NEXUS interview slot found"'""".format(message))
            return  # Halt on first match

    logging.info(f"No openings for {location_name}")


def main() -> None:

    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", default=False)
    parser.add_argument("--tweet", action="store_true", default=False)
    args = parser.parse_args()

    logging.info(f"Starting checks (locations: {len(LOCATIONS)})")
    for location_name, location_code in LOCATIONS:
        check_for_openings(location_name, location_code, args)


if __name__ == "__main__":

    logging.basicConfig(
        format=LOGGING_FORMAT,
        level=logging.INFO,
        stream=sys.stdout
    )

    main()
