from urllib import parse
from lxml import etree
from io import StringIO
from pprint import pprint

import requests


def get_torrent_listings(search_term, catagory_int):
    """
    Primary method for gettings torrents, returns a listing of them after
        scraping and filtering them

    search_term :: search term string, ex 'iron man 2008'
    """

    # Format the URL with with the encoded search term and send the GET request
    search_results_url = 'https://thepiratebay.org/search/{}/0/99/{}'.format(parse.quote(search_term.lower().strip()),
                                                                             catagory_int)
    results_response = requests.get(search_results_url)

    # Get all the row listings from the page
    raw_results = scrape_torrents(results_response)
    # Filter and prettify the listings
    filtered_results = filter_and_clean(raw_results)

    # The final list of dicts representing each torrent
    return filtered_results


def scrape_torrents(response):
    """ Scrapes the raw listing from the requests response"""

    parser = etree.HTMLParser()
    tree = etree.parse(StringIO(response.text), parser)

    # This is the XPATH that returns all the rows we want
    TABLE_ROWS = '//table[@id="searchResult"]//tr'
    # These are the fields we expect to find in each row
    ROW_FIELDS = {
        'name': 'td[2]/div/a/text()',
        'link': 'td[2]/div/a/@href',
        'magnet': 'td[2]/a/@href',
        'torrent_details': 'td[2]/font/text()',
        'seeders': 'td[3]/text()',
        'leechers': 'td[4]/text()',
    }

    results = []
    for row in tree.xpath(TABLE_ROWS):
        result = {}

        for field in ROW_FIELDS:
            scraped_value = row.xpath(ROW_FIELDS[field])

            # Unpack lists with single items
            if isinstance(scraped_value, list) and len(scraped_value) == 1:
                scraped_value = scraped_value[0]

            # Ex {'name': 'scraped value from name field', etc...}
            result[field] = scraped_value

        # Only append the result if a string was scraped for the torrent name
        # (Table header rows, etc don't contain strings and return [])
        if isinstance(result['name'], str):
            results.append(result)

    return results


def filter_and_clean(raw_results):
    """Filters and prettifies individual scraped torrent items, returning a list"""

    results_cleaned = []
    for result in raw_results:
        result['link'] = 'https://thepiratebay.org' + result['link']

        result['torrent_details'] = result['torrent_details'].replace(u'\xa0', u' ')
        result['upload_date'], result['file_size'] = result['torrent_details'].split(', ')[:2]
        del result['torrent_details']
        result['upload_date'] = result['upload_date'].replace('Uploaded', '').strip().replace(" ", "-")
        result['file_size'] = result['file_size'].replace('Size', '').strip()

        """ Converting the file size to kilobytes """
        if result['file_size'].split(' ')[1] not in ['KiB', 'MiB', 'GiB']:
            continue
        elif result['file_size'].split(' ')[1] == 'KiB':
            result['file_size'] = int(float(result['file_size'].split(' ')[0]))
        elif result['file_size'].split(' ')[1] == 'MiB':
            result['file_size'] = int(float(result['file_size'].split(' ')[0]) * 1024)
        elif result['file_size'].split(' ')[1] == 'GiB':
            result['file_size'] = int(float(result['file_size'].split(' ')[0]) * 1024 * 1024)

        results_cleaned.append(result)

    return results_cleaned


if __name__ == '__main__':
    torrents = get_torrent_listings('iron man 2008', 207)[0]
    pprint(torrents)
