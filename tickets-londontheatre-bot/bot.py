#!/usr/bin/env python

import argparse
import csv
import datetime
import logging

from bs4 import BeautifulSoup
import requests

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


# Utility functions
def daterange(start_date, end_date):
    '''
    Iterator for a range of dates
    '''
    for n in range(int ((end_date - start_date).days)):
        yield start_date + datetime.timedelta(n)

def parseHtml(html_page):
    '''
    Parse a HTML page into a list of dicts    
    '''
    logger.debug("Parsing HTML page")
    soup = BeautifulSoup(html_page, "html.parser")
    table = soup.find("table", attrs={"data-id": "seats-table"})
    tickets = []
    if table:
        for row in table.tbody.find_all("tr"):
            cols = row.find_all("td")
            ticket = {
                "time": cols[0].text,
                "area": cols[1].div.text,
                "seats": cols[2].span.text,
                "price": cols[3].find(text=True, recursive=False)
            }
            tickets.append(ticket)
    else:
        logger.debug("No tickets data table found in page")
    return tickets


# Main script


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
        self.dateTo = dateTo if dateTo else (datetime.date.today() + datetime.timedelta(90))

    def requestHtmlSingle(self, single_date):
        '''
        Get a single string representing the HTML contents of the page on a single date
        '''
        self.logger.debug("Getting single HTML page")
        complete_url = 'http://tickets.londontheatre.co.uk/book/availability/{showId}/134/{ticketQuantity}?bookingDate={ticketDate}&type={ticketType}'.format(
                        ticketDate=single_date.strftime("%Y%m%d"),
                        showId=self.showId,
                        ticketQuantity=self.ticketQuantity,
                        ticketType='A')
        logger.debug("Getting HTML")
        r = requests.get(complete_url)
        return r.text

    def requestTicketsSingle(self, single_date):
        '''
        Get a list of dictionaries with tickets available on a single date
        '''
        html = self.requestHtmlSingle(single_date)
        tickets = parseHtml(html)
        rows = [dict(date=single_date.strftime("%Y%m%d"), showId=self.showId, **ticket) for ticket in tickets]
        return rows

    def requestTickets(self):
        tickets = []
        for single_date in daterange(self.dateFrom, self.dateTo):
            tickets.extend(self.requestTicketsSingle(single_date))
        return tickets


def main_parser():
    logger.debug("Generating argument parser")
    parser = argparse.ArgumentParser(description="Scrape tickets.londontheatre.co.uk")
    parser.add_argument("outfile", help="CSV file to write tickets data to")
    parser.add_argument("showId", help="ID of show to scrape")
    parser.add_argument("-n", "--number-tickets", default=2, type=int, help="Number of tickets required")
    parser.add_argument("-f", "--from-date", default=None, help="Date YYYYMMDD to search from (inclusive)")
    parser.add_argument("-t", "--to-date", default=None, help="Date YYYMMDD to search to (exclusive)")
    return parser

def main():
    parser = main_parser()
    args = parser.parse_args()

    dateFrom, dateTo = [datetime.datetime.strptime(date_string, "%Y%m%d").date() if date_string else date_string for date_string in [args.from_date, args.to_date]]
    ltlBot = Bot(args.showId,
                ticketQuantity=args.number_tickets,
                dateFrom=dateFrom,
                dateTo=dateTo)
    ticketRows = ltlBot.requestTickets()
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

if __name__ == "__main__":
    main()