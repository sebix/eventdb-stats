#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 16 17:45:45 2018

@author: sebastian
"""
import argparse
import configparser


VERSION = '0.1'

TRACE = """
var {section} = {
  x: {x},
  y: {y},
  name: '{name}',
  type: 'bar',
};
"""


def read_config(filename):
    config = configparser.ConfigParser()
    config.read(filename)
    return config


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
                        help='output file')

    args = parser.parse_args()
    config = read_config(args.config)


if __name__ == '__main__':
    main()
