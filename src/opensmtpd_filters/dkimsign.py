import argparse
import email
import re
import sys

from dkim import dkim_sign

from .opensmtpd import FilterServer

def start():
    parser = argparse.ArgumentParser(description='DKIM signing filter for OpenSMTPD.')
    parser.add_argument('--config', '-c', metavar='config_path', help='Config file listing domain configurations (one per line)')
    parser.add_argument('domains', nargs='*', metavar='domain:selector:key_path', help='Domain configuration')
    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r') as input:
            for line in input:
                line = line.strip()
                if line:
                    args.domains.append(line)
    if not args.domains:
        parser.print_help()
        sys.exit(1)

    config = {}
    for entry in args.domains:
        domain, selector, key = entry.split(':', 2)
        config[domain] = {'selector': selector, 'key': key}

    server = FilterServer()
    server.register_message_filter(lambda context, lines: sign(config, lines))
    server.serve_forever()


def sign(config, lines):
    parsed = email.message_from_string('\n'.join(lines))
    sender = parsed.get('from', '')
    match = re.search(r'<([^<>]+)>', sender)
    if match:
        sender = match.group(1)
    domain = re.sub(r'.*@', '', sender)
    if domain in config:
        with open(config[domain]['key'], 'rb') as input:
            key = input.read()
        signature = dkim_sign(
            '\n'.join(lines).encode('latin-1'),
            config[domain]['selector'].encode('latin-1'),
            domain.encode('latin-1'),
            key
        ).decode('latin-1')
        header, value = re.split(r':\s*', signature, 1)
        parsed[header] = value
        lines = re.split(r'\r?\n', parsed.as_string())
        if lines[-1] == '':
            lines.pop()
    return lines
