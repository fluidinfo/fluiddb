import os
import re
from setuptools import setup


def findPackages(moduleName):
    # implement a simple findPackages so we don't have to depend on
    # Twisted's getPackages
    packages = []
    for directory, subdirectories, files in os.walk(moduleName):
        if '__init__.py' in files:
            packages.append(directory.replace(os.sep, '.'))
    return [package for package in packages
            if ('testing' not in package and 'test' not in package)]


def parseRequirements(filename):
    requirements = []
    for line in open(filename, 'r').read().split('\n'):
        if re.match(r'(\s*#)|(\s*$)', line):
            continue
        if re.match(r'\s*-e\s+', line):
            # TODO support version numbers
            requirements.append(re.sub(r'\s*-e\s+.*#egg=(.*)$', r'\1', line))
        elif re.match(r'\s*-f\s+', line):
            pass
        else:
            requirements.append(line)

    return requirements


def parseDependencyLinks(filename):
    dependencyLinks = []
    for line in open(filename, 'r').read().split('\n'):
        if re.match(r'\s*-[ef]\s+', line):
            dependencyLinks.append(re.sub(r'\s*-[ef]\s+', '', line))

    return dependencyLinks


setup(name='fluiddb',
      version='0.1',
      description='FluidDB',
      author='Fluidinfo',
      author_email='fluiddb-dev@googlegroups.com',
      packages=findPackages('fluiddb'),
      url='https://github.com/fluidinfo/fluiddb',
      classifiers=[
          'Development Status :: 6 - Mature',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX',
          'Topic :: Database :: Database Engines/Servers',
      ],
      install_requires=parseRequirements('requirements.txt'),
      dependency_links=parseDependencyLinks('requirements.txt'),
      data_files=[('twisted/plugins', ['twisted/plugins/fluiddb_plugin.py'])],
      scripts=['bin/fluidinfo'])
