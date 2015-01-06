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


def install(packages):
    streams = _run_command(['install'] + packages)
    return streams._stdout_stream.getvalue()


def uninstall(packages, verbose=True):
    streams = _run_command(['uninstall'] + packages)
    return streams._stdout_stream.getvalue()


def freeze():
    streams = _run_command(['freeze'])
    return sorted([v for v in streams._stdout_stream.getvalue().splitlines()
                   if v and not v.startswith('#')])


def _run_command(*args):
    # Find the dictionary of pip commands. In newer version of pip,
    # the commands are stored in a dictionary called 'commands dict'
    # and there is a submodule called commands. In older versions,
    # the dictionary is called 'commands'.
    try:
        commands_dict = getattr(pip, 'commands_dict')
    except AttributeError:
        commands_dict = getattr(pip, 'commands')

    try:
        cmd_name, options, args, parser = pip.parseopts(*args)
        command = commands_dict[cmd_name](parser)
    except ValueError:
        cmd_name, args = pip.parseopts(*args)
        command = commands_dict[cmd_name]()
        options = None
    streams = CaptureStdStreams()
    with streams:
        if options is None:
            exit_status = command.main(args[1:])
        else:
            exit_status = command.main(args[1:], options)
    if exit_status != 0:
        raise RuntimeError(streams._stderr_stream.getvalue())
    return streams
