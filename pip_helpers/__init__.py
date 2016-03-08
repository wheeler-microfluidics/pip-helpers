from collections import OrderedDict
import cStringIO as StringIO
import json
import re
import sys

import natsort
import pip
import requests


COMPARE_PATTERN = r'(!=|==|>=|<=|>|<)'
CRE_PACKAGE = re.compile(r'''
    ^(?P<name>[_a-zA-Z][\w_]+)\s*
     (?P<version_specifiers>
      {compare_pattern}\s*[\w\._]+
      (\s*,\s*{compare_pattern}
       \s*[\w\._]+)*)?$'''.format(compare_pattern=COMPARE_PATTERN), re.VERBOSE)

CRE_VERSION_SPECIFIERS = re.compile(r'(?P<comparator>{compare_pattern})'
                                    r'\s*(?P<version>[\w\._]+)'
                                    .format(compare_pattern=COMPARE_PATTERN),
                                    re.VERBOSE)


def get_releases(package_str, pre=False, key=None,
                 server_url='https://pypi.python.org/pypi/{}/json'):
    '''
    Query Python Package Index for list of available release for specified
    package.

    Args
    ----

        package_str (str) : Name of package hosted on Python package index.
            Version constraints are also supported (e.g., `"foo", "foo==1.0",
            "foo>=1.0"`, etc.)  See [version specifiers][1] reference for more
            details.

    Returns
    -------

        (collections.OrderedDict) : Package release information, indexed by
            package version string and ordered by upload time (i.e., most
            recent release is last).


    [1]: https://www.python.org/dev/peps/pep-0440/#version-specifiers
    '''
    match = CRE_PACKAGE.match(package_str)
    if not match:
        raise ValueError('Invalid package descriptor. Must be like "foo", '
                         '"foo==1.0", "foo>=1.0", etc.')
    package_request = match.groupdict()

    response = requests.get(server_url.format(package_request['name']))
    package_data = json.loads(response.text)

    if key is None:
        key = lambda (k, v): v['upload_time']

    all_releases = OrderedDict(sorted([(k, v[0]) for k, v in
                                       package_data['releases'].iteritems()],
                                      key=key))

    if not all_releases:
        raise KeyError('No releases found for package: {}'
                       .format(package_request['name']))

    match_dict = match.groupdict()
    if match_dict['version_specifiers']:
        comparators = [m.groupdict() for m in CRE_VERSION_SPECIFIERS
                       .finditer(match_dict['version_specifiers'])]
    else:
        comparators = []

    filter_ = lambda v: (True if not comparators
                         else all(eval('%r %s %r' %
                                       (natsort.natsort_key(v),
                                        c['comparator'],
                                        natsort.natsort_key(c['version'])))
                                  for c in comparators))

    # Define regex to check for pre-release.
    cre_pre = re.compile(r'\.dev|\.pre')
    releases = OrderedDict([(k, v) for k, v in all_releases.iteritems()
                            if filter_(k) and (pre or not cre_pre.search(k))])
    if not releases:
        raise KeyError('None of the following releases match the specifiers '
                       '"{}": {}'.format(package_request['version_specifiers'],
                                         ', '.join(all_releases.keys())))
    return releases


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


def uninstall(packages):
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
            exit_status = command.main(args)
        else:
            exit_status = command.main(args, options)
    if exit_status != 0:
        raise RuntimeError(streams._stderr_stream.getvalue())
    return streams
