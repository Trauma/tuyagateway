import codecs
import os
import sys
import runpy

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

version_meta = runpy.run_path("./version.py")
VERSION = version_meta["__version__"]

PACKAGE_NAME = "tuyagateway"


if len(sys.argv) <= 1:
    print(
        """
Suggested setup.py parameters:
    * build
    * install
    * sdist  --formats=zip
    * sdist  # NOTE requires tar/gzip commands
PyPi:
    twine upload dist/*
"""
    )

here = os.path.abspath(os.path.dirname(__file__))

readme_filename = os.path.join(here, "README.md")
if os.path.exists(readme_filename):
    with codecs.open(readme_filename, encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = None


def parse_requirements(filename):
    """Load requirements from a pip requirements file."""
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]


setup(
    name=PACKAGE_NAME,
    author="tradeface",
    version=version_meta["__version__"],
    description="Python middleware for Tuya WiFi smart devices to MQTT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=f"https://github.com/TradeFace/{PACKAGE_NAME}/",
    scripts=[f"scripts/{PACKAGE_NAME}"],
    author_email="",
    data_files=[("etc", ["etc/tuyagateway.conf", "etc/tuyagateway.service"]),],
    license="Unlicense",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Home Automation",
        "License :: Public Domain",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Topic :: Home Automation",
    ],
    keywords="home automation, mqtt, auto discovery, tuya",
    packages=find_packages(),
    platforms="any",
    install_requires=parse_requirements("requirements.txt"),
)
