#
# parakeet.command_line.sample.add_molecules.py
#
# Copyright (C) 2019 Diamond Light Source and Rosalind Franklin Institute
#
# Author: James Parkhurst
#
# This code is distributed under the GPLv3 license, a copy of
# which is included in the root directory of this package.
#


import logging
import time
import parakeet.io
import parakeet.command_line
import parakeet.config
import parakeet.sample
from argparse import ArgumentParser
from typing import List


__all__ = ["add_molecules"]


# Get the logger
logger = logging.getLogger(__name__)


def get_description():
    """
    Get the program description

    """
    return "Add molecules to the sample model"


def get_parser(parser: ArgumentParser = None) -> ArgumentParser:
    """
    Get the add molecules parser

    """

    # Initialise the parser
    if parser is None:
        parser = ArgumentParser(description=get_description())

    # Add some command line arguments
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        dest="config",
        required=True,
        help="The yaml file to configure the simulation",
    )
    parser.add_argument(
        "-s",
        "--sample",
        type=str,
        default="sample.h5",
        dest="sample",
        help="The filename for the sample file",
    )

    return parser


def add_molecules_impl(args):
    """
    Add molecules to the sample

    """

    # Get the start time
    start_time = time.time()

    # Configure some basic logging
    parakeet.command_line.configure_logging()

    # Do the work
    parakeet.sample.add_molecules(args.config, args.sample)

    # Print output
    logger.info("Time taken: %.1f seconds" % (time.time() - start_time))


def add_molecules(args: List[str] = None):
    """
    Add molecules to the sample

    """
    add_molecules_impl(get_parser().parse_args(args=args))
