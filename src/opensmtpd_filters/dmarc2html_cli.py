import argparse
from .dmarc2html import process_report

def run():
    parser = argparse.ArgumentParser(prog='dmarc2html', description='DMARC aggregate report to HTML converter')
    parser.add_argument('report_file', help='Path of the DMARC aggregate report file')
    args = parser.parse_args()
    print(process_report(args.report_file))
