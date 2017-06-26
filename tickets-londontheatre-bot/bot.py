#!/usr/bin/env python

import argparse
from bs4 import BeautifulSoup
import requests
from datetime import timedelta, date
import csv
import logging

# Setup logging
logger = logging.getLogger('tickets-londontheatre-bot')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)

# Global variables
# 6168 is show ID for Hamlet
url_template = 'http://tickets.londontheatre.co.uk/book/availability/6168/134/2?bookingDate={date}&type=E'

# date range 29/06/2017 - 02/09/2017
start_date = date(2017, 6, 29)
end_date = date(2017, 9, 3)


# Utility functions
def daterange(start_date, end_date):
    '''
    Iterator for a range of dates
    '''
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)


# Main script

def html_page_for_date(single_date):
    '''
    Get a single string representing the HTML contents of the page on a single date
    '''
    logger.debug("Getting single HTML page; {0}".format(single_date))
    date_argument = single_date.strftime("%Y%m%d")
    complete_url = url_template.format(date=date_argument)
    logger.info("Processing date; {0}".format(date_argument))
    logger.debug("GETting HMTL")
    r = requests.get(complete_url)
    return r.text

def html_page_to_rows(single_date, html_page):
    '''
    Parse a HTML page into a list of dicts representing available tickets    
    '''
    logger.debug("Parsing HTML")
    soup = BeautifulSoup(html_page, "html.parser")
    table = soup.find("table", attrs={"data-id": "seats-table"})
    tickets = []
    if table:
        for row in table.tbody.find_all("tr"):
            cols = row.find_all("td")
            ticket = {}
            ticket["date"] = single_date
            ticket["time"] = cols[0].text
            ticket["area"] = cols[1].div.text
            ticket["seats"] = cols[2].span.text
            ticket["price"] = cols[3].find(text=True, recursive=False)
            tickets.append(ticket)
    else:
        logger.debug("No tickets data table found. Tickets available?")
    return tickets



def main_parser():
    logger.debug("Generating argument parser")
    parser = argparse.ArgumentParser(description="Scrape tickets.londontheatre.co.uk")
    parser.add_argument("outfile",
                        help="CSV file to write tickets data to")
    return parser

def main():
    parser = main_parser()
    args = parser.parse_args()
    outfile = args.outfile
    ticket = {
        "date": "",
        "time": "",
        "area": "",
        "seats": "",
        "price": ""
    }
    logger.info("Writing tickets file; {0}".format(outfile))
    with open(outfile, 'w') as fh:
        writer = csv.DictWriter(fh, ticket.keys(), quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for single_date in daterange(start_date, end_date):
            html = html_page_for_date(single_date)
            tickets = html_page_to_rows(single_date, html)
            for ticket in tickets:
                logger.debug("Writing row")
                writer.writerow(ticket)

if __name__ == "__main__":
    main()