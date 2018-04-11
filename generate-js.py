#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 16 17:45:45 2018

@author: sebastian
"""
import argparse
import collections
import configparser
import datetime
import sys

import psycopg2


VERSION = '0.1'

TRACE = """
var trace_{section_name}_{trace_name} = {{
  x: {x},
  y: {y},
  name: '{trace_title}',
  type: 'bar',
}};
"""
GRAPH = """<div id="{section_name}" style="width:{width};height:{height};"></div>"""
PLOT = """
{traces}

var data_{section_name} = [{traces_list}];

var layout_{section_name} = {{
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

Plotly.newPlot('{section_name}', data_{section_name}, layout_{section_name});
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
            self.__dict__[key] = psycopg2.connect(dsn=key).cursor()
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
    parser.add_argument('-c', '--config',
                        help='configuration file to use',
                        default=None)
    parser.add_argument('-o', '--output',
                        help='output file, default: - for stdout',
                        default='-')
    parser.add_argument('--dsn',
                        help='DSN connection string',
                        default=None)
    parser.add_argument('-q', '--query',
                        help='SQL Query',
                        default=None)

    args = parser.parse_args()
    if args.config:
        config = configparser.ConfigParser()
        config.read(args.config)
    else:
        if not args.dsn and args.query:
            sys.exit('For cli mode you must give both DSN and query string.')
        config = {
            'manual': {
                'dsn': args.dsn,
                'query': args.query,
                }
            }
    graphs = []
    plots = []
    for section_name, section in config.items():
        if section_name == 'DEFAULT':
            continue
        title = section.get('title', '')
        width = section.get('width', 1000)
        height = section.get('height', 500)
        dsn = args.dsn if args.dsn else section['dsn']
        db = CONNECTIONS[dsn]
        print('Starting query for %s: %r' % (section_name, section['query']), file=sys.stderr)
        db.execute(section['query'])
        data = collections.defaultdict(lambda: ([], []))
        for row in db:
            row_x = row[0]
            row_y = row[-1]
            row_names = tuple(str(x) for x in row[1:-1])  # For None/NULL values
            if isinstance(row_x, datetime.datetime):
                row_x = row_x.isoformat()
            data[row_names][0].append(row_x)
            data[row_names][1].append(row_y)
        traces = []
        for trace_names, trace_data in data.items():
            traces.append(TRACE.format(section_name=section_name, trace_name='_'.join(trace_names),
                                       trace_title=' '.join(trace_names),
                                       x=trace_data[0], y=trace_data[1]))

        graphs.append(GRAPH.format(section_name=section_name, width=width, height=height))
        plots.append(PLOT.format(section_name=section_name,
                                 width=width, height=height,
                                 title=title,
                                 traces_list=', '.join(['trace_%s_%s' % (section_name, '_'.join(trace_name)) for trace_name in data.keys()]),
                                 traces='\n'.join(traces),
                                 barmode=section.get('barmode', 'group')
                                 ))

    print('Rendering...', file=sys.stderr)
    plot = TEMPLATE.format(graphs='\n'.join(graphs),
                           plots='\n'.join(plots),
                           )
    if args.output == '-':
        print(plot)
    else:
        with open(args.output, 'w') as output_handle:
            output_handle.write(plot)


if __name__ == '__main__':
    main()
