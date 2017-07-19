#!/usr/bin/env python

import argparse
import csv
import datetime
import logging
import re

from bs4 import BeautifulSoup
import requests
import six

# Setup logging
logger = logging.getLogger('tickets-londontheatre-bot')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)

# Global variables
# 6168 is show ID for Hamlet
# date range 29/06/2017 - 02/09/2017
validShowIdPattern = re.compile(r'^\d{4}$')

# Utility functions
def daterange(start_date, end_date):
    '''
    Iterator for a range of dates
    '''
    for n in range(int ((end_date - start_date).days)):
        yield start_date + datetime.timedelta(n)

def requestHtml(url):
    '''
    Request a HTML url and return the text content
    '''
    logger.debug("Getting HTML; {0}".format(url))
    r = requests.get(url, headers={'Host': "tickets.londontheatre.co.uk"})
    return r.text

# Main script

def availableShows():
    '''
    Find a dictionary of available shows
    '''
    logger.debug("Scraping a list of shows")
    html = requestHtml("http://tickets.londontheatre.co.uk/")
    soup = BeautifulSoup(html, "html.parser")
    selectList = soup.find("select", attrs={"id": "edit-show"})
    shows = {}
    for option in selectList.find_all("option"):
        showId = option['value']
        showName = option.text
        if re.match(validShowIdPattern, showId):
            shows[showName] = showId
        else:
            logger.debug("Discarding invalid showId; {0}".format(showId))
    return shows


class ShowDatePage(object):
    def __init__(self, showId, pageDate, ticketQuantity):
        self.logger = logging.getLogger('tickets-londontheatre-bot.ShowDatePage')

        self.showId = showId
        self.pageDate = pageDate
        self.ticketQuantity = ticketQuantity

    def html(self):
        '''
        Get a single string representing the HTML contents of the page on a single date
        '''
        self.logger.debug("Getting ShowDate HTML page")
        complete_url = 'http://tickets.londontheatre.co.uk/book/availability/{showId}/134/{ticketQuantity}?bookingDate={ticketDate}&type={ticketType}'.format(
                        ticketDate=self.pageDate.strftime("%Y%m%d"),
                        showId=self.showId,
                        ticketQuantity=self.ticketQuantity,
                        ticketType='A')
        return requestHtml(complete_url)

    def tickets(self):
        '''
        Get a list of dictionaries with tickets available on a single date
        '''
        html = self.html()
        self.logger.debug("Parsing ShowDate page")

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", attrs={"data-id": "seats-table"})
        tickets = []
        if table:
            for row in table.tbody.find_all("tr"):
                cols = row.find_all("td")
                ticket = {
                    "time": cols[0].text,
                    "area": cols[1].div.text,
                    "seats": cols[2].span.text,
                    "price": cols[3].find(text=True, recursive=False),
                    "showId": self.showId,
                    "date": self.pageDate.strftime("%Y%m%d")
                }
                tickets.append(ticket)
        else:
            self.logger.debug("No tickets data table found in page")
        return tickets

class Bot(object):
    '''
    :param string showId: The unique ID used by tlt for each show.
    :param int ticketQuantity: The number of tickets required together.
    :param date dateFrom: A `datetime.date` object representing the start date of the search. Defaults to today.
    :param date dateTo: A `datetime.date` object representing the end (exclusive) date of the search. Defaults to today + 90 days.
    '''
    def __init__(self, showId, ticketQuantity=2, dateFrom=None, dateTo=None):
        self.logger = logging.getLogger('tickets-londontheatre-bot.Bot')

        self.showId = showId
        self.ticketQuantity = ticketQuantity

        self.dateFrom = dateFrom if dateFrom else datetime.date.today()
        self.dateTo = dateTo if dateTo else (self.dateFrom + datetime.timedelta(90))

    def tickets(self):
        tickets = []
        for i, single_date in enumerate(daterange(self.dateFrom, self.dateTo)):
            self.logger.info("Reading page {0} of tickets".format(i))
            page = ShowDatePage(self.showId, single_date, self.ticketQuantity)
            pageTickets = page.tickets()
            tickets.extend(pageTickets)
        return tickets

# Subcommands

def shows(args):
    logger.info("Looking for shows")
    showList = [k for k, v in six.iteritems(availableShows())]
    for show in sorted(showList):
        print(show)

def search(args):
    logger.info("Searching for tickets")
    # Interpret user input
    dateFrom, dateTo = [datetime.datetime.strptime(date_string, "%Y%m%d").date() if date_string else date_string for date_string in [args.from_date, args.to_date]]
    showId = availableShows()[args.show]
    logger.debug("Show name {0} is id {1}".format(args.show, showId))
    ltlBot = Bot(showId,
                ticketQuantity=args.number_tickets,
                dateFrom=dateFrom,
                dateTo=dateTo)
    ticketRows = ltlBot.tickets()
    fieldnames = sorted(list(set(k for d in ticketRows for k in d)))

    outfile = args.outfile
    logger.info("Writing tickets file; {0}".format(outfile))
    with open(outfile, 'w') as fh:
        logger.debug("Writing header")
        writer = csv.DictWriter(fh, fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        logger.debug("Writing ticket rows")
        for row in ticketRows:
            writer.writerow(row)

# Main

def main_parser():
    logger.debug("Generating argument parser")
    parser = argparse.ArgumentParser(description="Scrape tickets.londontheatre.co.uk")
    subparsers = parser.add_subparsers()

    parser_shows = subparsers.add_parser('shows')
    parser_shows.set_defaults(func=shows)
   
    parser_search = subparsers.add_parser('search')
    parser_search.set_defaults(func=search)
    parser_search.add_argument("outfile", help="CSV file to write tickets data to")
    parser_search.add_argument("show", help="Name of show to scrape")
    parser_search.add_argument("-n", "--number-tickets", default=2, type=int, help="Number of tickets required")
    parser_search.add_argument("-f", "--from-date", default=None, help="Date YYYYMMDD to search from (inclusive)")
    parser_search.add_argument("-t", "--to-date", default=None, help="Date YYYMMDD to search to (exclusive)")

    return parser

def main():
    parser = main_parser()
    args = parser.parse_args()
    logger.debug(args)
    try:
        args.func(args)
    except AttributeError as e:
        raise
        parser.parse_args(['-h'])

if __name__ == "__main__":
    main()