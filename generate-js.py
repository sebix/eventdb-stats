#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 16 17:45:45 2018

@author: sebastian
"""
import argparse
import configparser
import datetime
import sys

import psycopg2
import psycopg2.extras


VERSION = '0.1'

TRACE = """
var {section} = {{
  x: {x},
  y: {y},
  name: '{section}',
  type: 'bar',
}};
"""


class ConnectionCache(object):
    def __getitem__(self, key):
        if key not in self.__dict__:
            self.__dict__[key] = psycopg2.connect(dsn=key).cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return self.__dict__[key]
CONNECTIONS = ConnectionCache()


def main():
    parser = argparse.ArgumentParser(
        prog='eventdb stats',
        description="Generates a HTML file with JS that displays stats on the eventdb.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('-v', '--version',
                        action='version', version=VERSION)
    parser.add_argument('config', help='configuration file to use')
    parser.add_argument('-o', '--output',
                        help='output file, default: stdout',
                        default=sys.stdout)
    parser.add_argument('--dsn',
                        help='DSN connection string',
                        default=None)

    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read(args.config)
    traces = {}
    for trace_name, section in config.items():
        trace = {
            'title': section.get('title', ''),
            'width': section.get('width', ''),
            'height': section.get('height', ''),
            'dsn': args.dsn if args.dsn else section['dsn'],
            'x': [],
            'y': [],
            }
        if trace_name == 'DEFAULT':
            continue
        db = CONNECTIONS[trace['dsn']]
        print('Starting query for %s: %r' % (trace_name, section['query']), file=sys.stderr)
        db.execute(section['query'])
        for row in db:
            for rowkey, rowvalue in row.items():
                if rowkey == 'count':
                    trace['y'].append(rowvalue)
                else:
                    if isinstance(rowvalue, datetime.datetime):
                        rowvalue = rowvalue.isoformat()
                    trace['x'].append(rowvalue)
        traces[trace_name] = trace

    print('Rendering...', file=sys.stderr)
    with open('template.html') as template_handle:
        TEMPLATE = template_handle.read()
    print(TEMPLATE.format(width=trace['width'], height=trace['height'],
                          traces=TRACE.format(x=trace['x'], y=trace['y'], section=trace_name),
                          traces_list=trace_name, title=trace['title']))


if __name__ == '__main__':
    main()
