import cStringIO as StringIO
import sys

import pip


class RedirectStdStreams(object):
    def __init__(self, stdout=None, stderr=None):
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush()
        self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr


class CaptureStdStreams(RedirectStdStreams):
    def __init__(self):
        self._stdout_stream = StringIO.StringIO()
        self._stderr_stream = StringIO.StringIO()
        super(CaptureStdStreams, self).__init__(stdout=self._stdout_stream,
                                                stderr=self._stderr_stream)


def install(packages, verbose=True):
    cmd_name, options, args, parser = pip.parseopts(['install'] + packages)
    command = pip.commands['install'](parser)
    streams = CaptureStdStreams()
    with streams:
        exit_status = command.main(args[1:], options)
    if exit_status != 0:
        raise RuntimeError(streams._stderr_stream.getvalue())
    if verbose:
        return streams._stdout_stream.getvalue()
    else:
        return exit_status


def uninstall(packages, verbose=True):
    cmd_name, options, args, parser = pip.parseopts(['uninstall', '-y'] +
                                                    packages)
    command = pip.commands['uninstall'](parser)
    streams = CaptureStdStreams()
    with streams:
        exit_status = command.main(args[1:], options)
    if exit_status != 0:
        raise RuntimeError(streams._stderr_stream.getvalue())
    if verbose:
        return streams._stdout_stream.getvalue()
    else:
        return exit_status


def freeze():
    cmd_name, options, args, parser = pip.parseopts(['freeze'])
    command = pip.commands['freeze'](parser)
    streams = CaptureStdStreams()
    with streams:
        exit_status = command.main(args[1:], options)
    if exit_status == 0:
        return sorted([v for v in
                       streams._stdout_stream.getvalue().splitlines()
                       if v and not v.startswith('#')])
    else:
        raise RuntimeError(streams._stderr_stream.getvalue())
