#!/usr/bin/env python
"""
Setup for SQLAlchemy backend for DM
"""
from setuptools import find_packages, setup

setup_params = dict(
    name="dmSQLAlchemy",
    version='1.4.41',
    description="SQLAlchemy dialect for DM",
    author="Dameng",
    author_email="",
    keywords='DM SQLAlchemy',
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "sqlalchemy.dialects":
            ["dm = src.dmPython:DMDialect_dmPython", "dm.dmPython = src.dmPython:DMDialect_dmPython"]
    },
    install_requires=['dmPython', 'sqlalchemy>1.3.24, <2.0'],
)

if __name__ == '__main__':
    setup(**setup_params)
