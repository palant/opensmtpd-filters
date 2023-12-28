import argparse
import email
import email.message
import email.policy
import io
import re
import traceback

from .dmarc2html import process_report
from .opensmtpd import FilterServer

def start():
    parser = argparse.ArgumentParser(description='DMARC converter filter for OpenSMTPD.')
    parser.add_argument('name', help='Name of the account receiving DMARC aggregate reports')
    args = parser.parse_args()

    server = FilterServer()
    server.register_handler('report', 'tx-rcpt', save_rcpt)
    server.register_message_filter(lambda session, lines: convert(args.name, session, lines))
    server.serve_forever()


def save_rcpt(session, _, result, address):
    if result != 'ok':
        return
    session['rcpt'] = address


def convert(account_name, session, lines):
    try:
        recipient = re.sub(r'@.*', '', session['rcpt'])
        if recipient != account_name:
            return lines

        parsed = email.message_from_string('\n'.join(lines), policy=email.policy.default)
        parsed.make_mixed()

        attachments = [part for part in parsed.walk() if part.get_filename()]
        if len(attachments) != 1:
            raise Exception('Expected one named attachment, got {}'.format(len(attachments)))

        attachment = attachments[0]
        filename = attachment.get_filename()

        bytes = io.BytesIO(attachment.get_payload(decode=True))
        bytes.name = filename
        html = process_report(bytes)

        html_part = email.message.MIMEPart(policy=email.policy.default)
        html_part.set_content(html, subtype='html', charset='utf-8')

        parsed.set_payload([html_part, attachment])
        return parsed.as_string().strip().split('\n')
    except:
        traceback.print_exc()
        return lines
