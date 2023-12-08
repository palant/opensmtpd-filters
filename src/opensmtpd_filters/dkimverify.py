import argparse
import email
import re

from dkim import dkim_verify

from .opensmtpd import FilterServer

try:
    import spf
except:
    spf = None


def start():
    parser = argparse.ArgumentParser(description='DKIM verifying filter for OpenSMTPD.')
    parser.add_argument('hostname', nargs='?', default='localhost')
    args = parser.parse_args()

    server = FilterServer()
    server.register_handler('report', 'link-identify', save_identity)
    server.register_handler('report', 'tx-mail', save_sender)
    server.register_message_filter(lambda context, lines: verify(server, args.hostname, context, lines))
    server.serve_forever()


def save_identity(context, method, identity):
    context['identity'] = identity


def save_sender(context, message_id, result, sender):
    context['sender'] = sender


def verify(server, hostname, context, lines):
    message = '\n'.join(lines)
    parsed = email.message_from_string(message)
    if 'authentication-results' in parsed:
        del parsed['authentication-results']

    dkim_result = 'unknown'
    try:
        if 'dkim-signature' in parsed:
            if dkim_verify(message.encode('latin-1')):
                dkim_result = 'pass'
            else:
                dkim_result = 'fail'
    except:
        server.log_exception()

    if spf:
        try:
            ip = re.sub(r':\d+$', '', context['src'])
            ip = re.sub(r'^\[(.*)\]$', r'\1', ip)
            spf_result, code, message = spf.check(i=ip, s=context['sender'], h=context['identity'])
            clean = lambda value: re.sub(r'\s', '', value)
            spf_result = '{} (sender is {}/{}) smtp.mailfrom={}'.format(
                spf_result,
                clean(context['identity']),
                clean(ip),
                clean(context['sender'])
            )
        except:
            server.log_exception()
            spf_result = 'unknown'
        spf_result = '; spf={}'.format(spf_result)
    else:
        spf_result = ''

    parsed['Authentication-Results'] = '{}; dkim={}{}'.format(hostname, dkim_result, spf_result)
    return parsed.as_string().splitlines(False)
