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
import os.path
#import pprint
import re
import sys

import psycopg2


try:
    import plotly
except ImportError:
    plotly = None

VERSION = '0.1'

TRACE = """
var trace_{section_name}_{trace_name} = {{
  x: {x},
  y: {y},
  name: '{trace_title}',
  type: 'bar',
}};
"""
GRAPH_JS = """<div id="{section_name}" style="width:{width};height:{height};"></div>"""
GRAPH_PNG = """
<h2>{title}</h2>
<img src="{path}/{section_name}.png" width="{width}px" height="{height}px"></img>
"""
PLOT_JS = """
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
TEMPLATE_JS = """
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
TEMPLATE_PNG = """
<html>
<head>
</head>
<body>
{graphs}
</body>
</html>
"""


class ConnectionCache(object):
    def __getitem__(self, key):
        if key not in self.__dict__:
            self.__dict__[key] = psycopg2.connect(dsn=key).cursor()
        return self.__dict__[key]
CONNECTIONS = ConnectionCache()


def to_js_name(value):
    if isinstance(value, (list, tuple)):
        value = '_'.join(value)
    return re.sub('[^a-zA-Z0-9]+', '_', value)


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
    parser.add_argument('-J', '--js',
                        help='Use Javascript',
                        default=True,
                        action='store_const',
                        const=True,
                        )
    parser.add_argument('-P', '--png',
                        help='Use PNG',
                        default=False,
                        action='store_const',
                        const=True,
                        )

    args = parser.parse_args()
    if args.png:
        args.js = False
        if plotly is None:
            print('Needed plotly library is not installed.', file=sys.stderr)
            return 2
    if args.js:
        args.png = False
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
    successes = 0
    for section_name, section in config.items():
        if section_name == 'DEFAULT':
            successes += 1
            continue
        title = section.get('title', '')
        width = section.get('width', 1000)
        height = section.get('height', 500)
        dsn = args.dsn if args.dsn else section['dsn']
        if not dsn:
            print('Missing DSN!', file=sys.stderr)
            continue
        db = CONNECTIONS[dsn]
        print('Starting query for %s: %r' % (section_name, section['query']), file=sys.stderr)
        db.execute(section['query'])
        data = collections.defaultdict(lambda: ([], []))
        for row in db:
            row_x = row[0]
            row_y = row[-1]
            row_names = tuple(str(x) for x in row[1:-1])  # For None/NULL values
            if isinstance(row_x, (datetime.datetime, datetime.date, datetime.time)):
                row_x = row_x.isoformat()
            data[row_names][0].append(row_x)
            data[row_names][1].append(row_y)
        traces = []
#        pprint.pprint(data)
        for trace_names, trace_data in data.items():
            if args.js:
                traces.append(TRACE.format(section_name=section_name, trace_name=to_js_name(trace_names),
                                           trace_title=' '.join(trace_names),
                                           x=trace_data[0], y=trace_data[1]))
            else:
                traces.append(plotly.graph_objs.Scatter(x = trace_data[0],
                                                        y = trace_data[1],
                                                        mode = 'lines',
                                                        name = ' '.join(trace_names),
                                                        ))

        if args.js:
            graphs.append(GRAPH_JS.format(section_name=section_name, width=width, height=height))
            plots.append(PLOT_JS.format(section_name=section_name,
                                        width=width, height=height,
                                        title=title,
                                        traces_list=', '.join(['trace_%s_%s' % (section_name, to_js_name(trace_name)) for trace_name in data.keys()]),
                                        traces='\n'.join(traces),
                                        barmode=section.get('barmode', 'group')
                                        ))
        else:
            if args.output == '-':
                path = ''
            else:
                path = os.path.splitext(args.output)[0]
            if not os.path.exists(path) and not os.path.isdir(path):
                os.mkdir(path)
            elif not os.path.isdir(path):
                print('Output path %r already exists and is not a directory!', file=sys.stderr)
                break
            filename = '{path}/{section_name}.svg'.format(path=path, section_name=section_name)
            print(filename)
            plotly.offline.plot(traces, filename=filename, image_width=width, image_height=height,
                                image='svg')
            graphs.append(GRAPH_PNG.format(title=title,
                                           section_name=section_name,
                                           path=path,
                                           width=width, height=height))
        successes += 1

    if successes:
        print('Rendering...', file=sys.stderr)
        if args.js:
            template = TEMPLATE_JS
        else:
            template = TEMPLATE_PNG
        plot = template.format(graphs='\n'.join(graphs),
                               plots='\n'.join(plots),
                               )
        if args.output == '-':
            print(plot)
        else:
            with open(args.output, 'w') as output_handle:
                output_handle.write(plot)
    elif config:  # something is configured and nothing could be completed
        print('Errors happend, could not render.', file=sys.stdout)
        return 1
    else:
        print('Nothing to do.')

if __name__ == '__main__':
    sys.exit(main())
