#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="PhlyGreen",
    version="0.0.1",
    author="Riccardo Malpica Galassi",
    author_email="riccardo.malpicagalassi@uniroma1.it",
    description="A collection of tools for the preliminary design of novel aircraft concepts for a more sustainable air mobility",
    url="https://github.com/rmalpica/PhlyGreen",
    packages=find_packages(),            
    include_package_data=True,
    python_requires=">=3",
    install_requires=["numpy", "matplotlib", "scipy"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
