# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import os


def strip_comments(l):
    return l.split('#', 1)[0].strip()


def get_version(version_tuple):
    if not isinstance(version_tuple[-1], int):
        return '.'.join(map(str, version_tuple[:-1])) + version_tuple[-1]
    return '.'.join(map(str, version_tuple))


init = os.path.join(os.path.dirname(__file__), 'src', 'solrq', '__init__.py')
version_line = list(filter(lambda l: l.startswith('VERSION'), open(init)))[0]
VERSION = get_version(eval(version_line.split('=')[-1]))

INSTALL_REQUIRES = []
README = os.path.join(os.path.dirname(__file__), 'README.md')
PACKAGES = find_packages('src')
PACKAGE_DIR = {'': 'src'}


def readme():
    return open(README, 'r').read()  # noqa


setup(
    name='solrq',
    version=VERSION,
    author='Michał Jaworski',
    author_email='swistakm@gmail.com',
    description='Python Solr query utility',
    long_description=readme(),
    long_description_content_type='text/markdown',

    packages=PACKAGES,
    package_dir=PACKAGE_DIR,

    url='https://github.com/swistakm/solrq',
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    zip_safe=True,

    license="BSD",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
    ],
)
