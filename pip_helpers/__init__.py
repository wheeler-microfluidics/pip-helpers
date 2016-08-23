from collections import OrderedDict
import json
import re
import subprocess as sp
import sys
try:
    import xmlrpclib
except ImportError:
    import xmlrpc.client as xmlrpclib

import natsort
import pkg_resources
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

DEFAULT_SERVER_URL = 'https://pypi.python.org/pypi/{}/json'
DEFAULT_HIDDEN_URL = 'https://pypi.python.org/pypi/'


def get_releases(package_str, pre=False, key=None, include_hidden=False,
                 server_url=DEFAULT_SERVER_URL, hidden_url=None):
    '''
    Query Python Package Index for list of available release for specified
    package.

    Parameters
    ----------
    package_str : str
        Name of package hosted on Python package index. Version constraints are
        also supported (e.g., ``"foo", "foo==1.0", "foo>=1.0"``, etc.).  See
        `version specifiers`_ reference for more details.
    pre : bool, optional
        Include pre-release packages.
    key : function, optional
        Key function to sort ``(package_name, release_info)`` items by.
    include_hidden : bool, optional
        Include "hidden" packages.
    server_url : str, optional
        URL to JSON API (default=``'https://pypi.python.org/pypi/{}/json'``).
    hidden_url : str, optional
        URL to XMLRPC API (default=``'https://pypi.python.org/pypi/'`` for PyPI
        server URL).

    Returns
    -------
    (string, collections.OrderedDict)
        Package name and package release information, indexed by package
        version string and ordered by upload time (i.e., most recent release is
        last).


    .. _version specifiers:
        https://www.python.org/dev/peps/pep-0440/#version-specifiers
    '''
    if all([not include_hidden, hidden_url is None, server_url ==
            DEFAULT_SERVER_URL]):
        hidden_url = DEFAULT_HIDDEN_URL
    if hidden_url is None:
        include_hidden = True

    match = CRE_PACKAGE.match(package_str)
    if not match:
        raise ValueError('Invalid package descriptor. Must be like "foo", '
                         '"foo==1.0", "foo>=1.0", etc.')
    package_request = match.groupdict()

    response = requests.get(server_url.format(package_request['name']))
    package_data = json.loads(response.text)

    if not include_hidden:
        client = xmlrpclib.ServerProxy(hidden_url)
        public_releases = set(client.package_releases(package_request['name']))

    if key is None:
        key = lambda (k, v): pkg_resources.parse_version(k)

    all_releases = OrderedDict(sorted([(k, v[0]) for k, v in
                                       package_data['releases'].iteritems()
                                       if include_hidden or k in
                                       public_releases], key=key))

    if not all_releases:
        raise KeyError('No releases found for package: {}'
                       .format(package_request['name']))

    package_request = match.groupdict()
    if package_request['version_specifiers']:
        comparators = [m.groupdict() for m in CRE_VERSION_SPECIFIERS
                       .finditer(package_request['version_specifiers'])]
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
    return package_request['name'], releases


def install(packages, capture_streams=True):
    '''
    Install the specified list of packages from the Python Package Index.

    Parameters
    ----------
    packages : list
        List of package descriptors (e.g., ``"foo", "foo==1.0", "foo>=1.0"``).
    capture_streams : bool, optional
        If ``True``, capture ``stdout`` and ``stderr`` output and instead print
        concise progress indicator.

    Returns
    -------
    str
        Combined output to ``stdout`` and ``stderr``.
    '''
    return _run_command('install', *packages, capture_streams=capture_streams)


def uninstall(packages, capture_streams=True):
    '''
    Uninstall the specified list of Python packages

    Parameters
    ----------
    packages : list
        List of package names (e.g., ``"foo"``, but not ``"foo==1.0",
        "foo>=1.0"``).
    capture_streams : bool, optional
        If ``True``, capture ``stdout`` and ``stderr`` output and instead print
        concise progress indicator.

    Returns
    -------
    str
        Combined output to ``stdout`` and ``stderr``.
    '''
    return _run_command('uninstall', *(['-y'] + list(packages)),
                        capture_streams=capture_streams)


def freeze():
    '''
    Return sorted list of package descriptors (e.g., ``"foo", "foo==1.0",
    "foo>=1.0"``), one descriptor for each installed package.
    '''
    output = _run_command('freeze', capture_streams=False)
    return sorted([v for v in output.splitlines()
                   if v and not v.startswith('#')])


def _run_command(*args, **kwargs):
    '''
    Run ``pip`` with the specified arguments.

    Parameters
    ----------
    capture_streams : bool, optional
        If ``True``, capture ``stdout`` and ``stderr`` output and instead print
        concise progress indicator.  (default=``False``)
    ostream : file-like, optional
        Write ``stdout`` and ``stderr`` to ``ostream``.

    Returns
    -------
    str
        Combined output to ``stdout`` and ``stderr``.
    '''
    capture_streams = kwargs.pop('capture_streams', False)
    ostream = kwargs.pop('ostream', sys.stdout)

    # Install required packages using `pip`, with Wheeler Lab wheels server
    # for binary wheels not available on `PyPi`.
    process_args = (sys.executable, '-m', 'pip') + args
    process = sp.Popen(process_args, stdout=sp.PIPE, stderr=sp.STDOUT,
                       shell=True)
    lines = []
    for stdout_i in iter(process.stdout.readline, b''):
        if capture_streams:
            ostream.write('.')
        lines.append(stdout_i)
    process.wait()
    print >> ostream, ''
    output = '\n'.join(lines)
    if process.returncode != 0:
        raise RuntimeError(output)
    return output
