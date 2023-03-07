#!/usr/bin/env python3

import argparse
import datetime
import enum
import gzip
import os
import socket
from xml.dom import minidom
import zipfile

import jinja2


class Flags(enum.Flag):
    NONE = 0
    OPTIONAL = enum.auto()
    MULTI = enum.auto()
    INT = enum.auto()
    IP = enum.auto()
    TIME = enum.auto()


def extract_data(file):
    if isinstance(file, str):
        ext = os.path.splitext(file)[1]
    else:
        ext = os.path.splitext(file.name)[1]

    if ext == '.xml':
        if isinstance(file, str):
            with open(file, 'rb') as input:
                return minidom.parse(input)
        else:
            return minidom.parse(file)
    if ext == '.gz':
        with gzip.open(file, 'rb') as input:
            return minidom.parse(input)
    elif ext == '.zip':
        with zipfile.ZipFile(file, 'r') as zip:
            names = zip.namelist()
            if len(names) != 1:
                raise Exception('Expected one zip file entry, got {}'.format(len(names)))
            with zip.open(names[0], 'r') as input:
                return minidom.parse(input)

    raise Exception('Unsupported report file extension {}'.format(ext))


def process_xml(node, fields):
    result = {}
    for child in node.childNodes:
        if child.nodeType == child.ELEMENT_NODE and child.localName in fields:
            flags = fields[child.localName]
            subfields = None
            if isinstance(flags, dict):
                subfields = flags
                if '_flags' in subfields:
                    flags = subfields['_flags']
                else:
                    flags = Flags.NONE
            if subfields is not None:
                data = process_xml(child, subfields)
            else:
                data = ''
                for child2 in child.childNodes:
                    if child2.nodeType == child2.TEXT_NODE:
                        data += child2.data
                if Flags.INT in flags:
                    data = int(data)
                elif Flags.IP in flags:
                    try:
                        data += ' ({})'.format(socket.gethostbyaddr(data)[0])
                    except:
                        pass
                        
                elif Flags.TIME in flags:
                    data = datetime.datetime.fromtimestamp(int(data), tz=datetime.timezone.utc).isoformat(sep=' ').replace('+00:00', ' UTC')

            if Flags.MULTI in flags:
                result.setdefault(child.localName, []).append(data)
            else:
                result[child.localName] = data
    for name, flags in fields.items():
        if name.startswith('_'):
            continue
        if isinstance(flags, dict):
            flags = flags['_flags'] if '_flags' in flags else Flags.NONE
        if name not in result and Flags.OPTIONAL not in flags:
            raise Exception('Mandatory field {} missing in {}'.format(name, node.toxml()))
    return result


def parse_data(xml):
    root = xml.documentElement
    if root.localName != 'feedback':
        raise Exception('Expected document root to be <feedback>, got {}'.format(root.localName))
    return process_xml(root, {
        'report_metadata': {
            'org_name': Flags.NONE,
            'email': Flags.NONE,
            'extra_contact_info': Flags.OPTIONAL,
            'date_range': {
                'begin': Flags.TIME,
                'end': Flags.TIME,
            },
        },
        'record': {
            '_flags': Flags.MULTI,
            'row': {
                'source_ip': Flags.IP,
                'count': Flags.INT,
                'policy_evaluated': {
                    'disposition': Flags.NONE,
                    'dkim': Flags.NONE,
                    'spf': Flags.NONE,
                    'reason': {
                        '_flags': Flags.MULTI | Flags.OPTIONAL,
                        'type': Flags.NONE,
                        'comment': Flags.OPTIONAL,
                    },
                },
            },
            'auth_results': {
                'dkim': {
                    '_flags': Flags.MULTI | Flags.OPTIONAL,
                    'domain': Flags.NONE,
                    'result': Flags.NONE,
                    'selector': Flags.OPTIONAL,
                },
                'spf': {
                    '_flags': Flags.MULTI,
                    'domain': Flags.NONE,
                    'result': Flags.NONE,
                    'scope': Flags.OPTIONAL,
                },
            },
        }
    })


def produce_html(data):
    env = jinja2.Environment(loader=jinja2.PackageLoader('dmarc2html'), autoescape=True)
    template = env.get_template('output.html')
    return template.render(data)


def process_report(path):
    xml = extract_data(path)
    data = parse_data(xml)
    data['xml'] = xml.toxml()
    return produce_html(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='dmarc2html', description='DMARC aggregate report to HTML converter')
    parser.add_argument('report_file', help='Path of the DMARC aggregate report file')
    args = parser.parse_args()
    print(process_report(args.report_file))