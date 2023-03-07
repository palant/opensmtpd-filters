#!/usr/bin/env python3
import email
import email.message
import email.policy
import io
import traceback

from dmarc2html import process_report
from opensmtpd import FilterServer

def convert(lines):
    try:
        parsed = email.message_from_string('\n'.join(lines), policy=email.policy.default)
        if not parsed.is_multipart() and parsed.get_filename() is not None:
            parsed.make_mixed()
        if not parsed.is_multipart():
            raise Exception('Multipart message expected')

        attachments = [*parsed.iter_attachments()]
        if len(attachments) != 1:
            raise Exception('Expected one attachment, got {}'.format(len(attachments)))

        attachment = attachments[0]
        filename = attachment.get_filename(attachment)
        if filename is None:
            raise Exception('Attachment does not have a file name')

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

if __name__ == '__main__':
    server = FilterServer()
    server.register_message_filter(convert)
    server.serve_forever()
