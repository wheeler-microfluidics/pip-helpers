# pip-helpers #

Functions to perform common operations with the Python Package Index.

Example usage:

```python
    >>> import pip_helpers as ph
    >>>
    >>> # Install list of Python packages
    >>> stdout_and_stderr = ph.install(['numpy>=1.11.1', 'pandas<0.18.1'])
    ....
    >>> # Uninstall list of installed Python packages
    >>> stdout_and_stderr = ph.uninstall(['numpy', 'pandas'])
    .......................
    >>> # Get list of descriptors for installed Python packages
    >>> installed_package_descriptors = ph.freeze()
```


# Credits #

Written by Christian Fobel <christian@fobel.net>
