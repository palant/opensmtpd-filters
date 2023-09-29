#!/usr/bin/env python3
import os
import re
import sys
import traceback

class FilterServer:
    """Filter server implementation, communicates with OpenSMTPD via stdin and stdout."""

    def __init__(self):
        """Handles the initial communication with OpenSMTPD."""

        self._stdin = os.fdopen(sys.stdin.fileno(), 'r', encoding='latin-1', buffering=1)
        self._stdout = os.fdopen(sys.stdout.fileno(), 'w', encoding='latin-1', buffering=1)
        self._stderr = os.fdopen(sys.stderr.fileno(), 'w', encoding='latin-1', buffering=1)
        self._handlers = {}
        self._contexts = None
        while self.recv() != 'config|ready':
            pass


    def recv(self):
        """Low-level functionality. Receives one line from OpenSMTPD."""

        return self._stdin.readline().rstrip('\r\n')


    def send(self, line):
        """Low-level functionality. Sends one line to OpenSMTPD."""

        print(line, file=self._stdout)


    def log_exception(self):
        """Prints the current exception message to stderr."""
        traceback.print_exc(file=self._stderr)


    def register_handler(self, event, phase, handler):
        """Registers an event processor, has to be called before serve_forever().
        Supported event types are 'report' and 'filter'. Handlers for report
        events will receive session ID and phase-specific parameters as
        arguments, no response expected. Handlers for most filter events will
        receive the same parameters but have to return a result like 'proceed'
        or 'reject|550 Spam'. Handler for 'data-line' filter will receive an
        additional send_dataline handler as last parameter which can be called
        any number of times to send lines to OpenSMTPD. Return value is ignored
        for this filter.
        """

        key = '{}|{}'.format(event, phase)
        if key in self._handlers:
            raise Exception('Handler for {} is already registered'.format(key))
        self._handlers[key] = handler
        self.send('register|{}|smtp-in|{}'.format(event, phase))


    def _call_handlers(self, result_handler, event, phase, session, *args):
        key = '{}|{}'.format(event, phase)
        if key in self._handlers:
            try:
                if self._contexts is not None and key != 'report|link-connect':
                    session = self._contexts[session]
                result_handler(self._handlers[key](session, *args))
            except:
                self.log_exception()


    def _filter_response(self, version, kind, session, token, payload):
        if re.search(r'^0\.[1-4]$', version):
            self.send('|'.join([kind, token, session, payload]))
        else:
            self.send('|'.join([kind, session, token, payload]))


    def serve_forever(self):
        """Ends initialization phase and processes any requests coming from
        OpenSMTPD. This function never returns.
        """

        def noop(result):
            pass

        def send_filter_response(result):
            self._filter_response(version, 'filter-result', session, token, result)

        def send_dataline(line):
            self._filter_response(version, 'filter-dataline', session, token, line)

        self.send('register|ready')
        while True:
            line = self.recv()
            count = line.count('|')
            if count < 5:
                continue
            elif count == 5:
                event, version, timestamp, subsystem, phase, session = line.split('|', 5)
                payload = None
            else:
                event, version, timestamp, subsystem, phase, session, payload = line.split('|', 6)

            if event == 'report':
                args = []
                if payload is not None:
                    args = payload.split('|')
                if phase == 'tx-mail' and re.search(r'^0\.[1-4]$', version) and len(args) == 3:
                    # Older protocol versions had result and sender reversed
                    args[1], args[2] = (args[2], args[1])
                self._call_handlers(noop, event, phase, session, *args)
            elif event == 'filter':
                if payload is not None and '|' in payload:
                    token, payload = payload.split('|', 1)
                else:
                    token = payload
                    payload = None
                if phase == 'data-line':
                    self._call_handlers(noop, event, phase, session, payload, send_dataline)
                else:
                    args = []
                    if payload is not None:
                        args = payload.split('|')
                    self._call_handlers(send_filter_response, event, phase, session, *args)


    def track_context(self):
        """Calling this method before serve_forever() ensures that the first
        parameter passed to all handlers will be the session context rather
        than merely a session ID. A session context is a dict object containing
        the following keys by default: 'session', 'rdns', 'fcrdns', 'src',
        'dest'. These match the parameters of the link-connect report event.
        Handlers can add and modify context object at will.
        """
        if self._contexts is not None:
            return

        self._contexts = {}

        def handle_link_connect(session, rdns, fcrdns, src, dest):
            self._contexts[session] = dict(session=session, rdns=rdns, fcrdns=fcrdns, src=src, dest=dest)


        def handle_link_disconnect(context):
            del self._contexts[context['session']]


        self.register_handler('report', 'link-connect', handle_link_connect)
        self.register_handler('report', 'link-disconnect', handle_link_disconnect)


    def register_message_filter(self, handler):
        """Convenience method allowing to filter message bodies without
        registering multiple event handlers. The handler will be called with
        the session context and a list of message lines. It has to return a
        filtered list of lines. Note: this will call track_context().
        """

        def escape_line(line):
            if line.startswith('.'):
                return '.' + line
            else:
                return line

        def unescape_line(line):
            if line.startswith('..'):
                return line[1:]
            else:
                return line

        def handle_dataline(context, line, send_dataline):
            try:
                if line != '.':
                    context.setdefault('message_lines', []).append(unescape_line(line))
                else:
                    lines = handler(context, context.get('message_lines', []))
                    for l in lines:
                        send_dataline(escape_line(l))
                    send_dataline('.')
                    context.pop('message_lines', None)
            except:
                send_dataline('.')
                context['message_error'] = True
                context.pop('message_lines', None)
                raise


        def handle_commit(context, *args):
            if 'message_error' in context:
                del context['message_error']
                return 'reject|451 Internal server error'
            else:
                return 'proceed'


        self.track_context()
        self.register_handler('filter', 'data-line', handle_dataline)
        self.register_handler('filter', 'commit', handle_commit)
