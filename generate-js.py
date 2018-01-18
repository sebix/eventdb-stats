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
var {name} = {{
  x: {x},
  y: {y},
  name: '{name}',
  type: 'bar',
}};
"""
GRAPH = """<div id="{name}" style="width:{width};height:{height};"></div>"""
PLOT = """
{traces}

var data_{name} = [{traces_list}];

var layout_{name} = {{
    barmode: '{barmode}',
    legend: {{
    x: 0,
    y: 1.0,
    bgcolor: 'rgba(255, 255, 255, 0)',
    bordercolor: 'rgba(255, 255, 255, 0)'
  }},
  title: '{title}',
  width: {width},
  height: {height},
  }};

Plotly.newPlot('{name}', data_{name}, layout_{name});
"""
TEMPLATE = """
<html>
<head>
<script src="./plotly-latest.min.js"></script>
</head>
<body>
{graphs}
<script>
{plots}
</script>
</body>
</html>
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
                        default=None)
    parser.add_argument('--dsn',
                        help='DSN connection string',
                        default=None)

    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read(args.config)
    graphs = []
    plots = []
    for trace_name, section in config.items():
        traces = {}
        if trace_name == 'DEFAULT':
            continue
        trace = {
            'title': section.get('title', ''),
            'width': section.get('width', ''),
            'height': section.get('height', ''),
            'dsn': args.dsn if args.dsn else section['dsn'],
            'x': [],
            'y': [],
            }
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

        graphs.append(GRAPH.format(name=trace_name, width=trace['width'], height=trace['height']))
        plots.append(PLOT.format(name=trace_name,
                                 width=trace['width'], height=trace['height'],
                                 title=trace['title'],
                                 traces_list=trace_name,
                                 traces=TRACE.format(name=trace_name, x=trace['x'], y=trace['y']),
                                 barmode=section.get('barmode', 'group')
                                 ))

    print('Rendering...', file=sys.stderr)
    plot = TEMPLATE.format(graphs='\n'.join(graphs),
                           plots='\n'.join(plots),
                           title=trace['title'])
    if not args.output:
        print(plot)
    else:
        with open(args.output, 'w') as output_handle:
            output_handle.write(plot)


if __name__ == '__main__':
    main()
