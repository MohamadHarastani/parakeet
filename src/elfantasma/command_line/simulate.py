#
# elfantasma.command_line.simulate.py
#
# Copyright (C) 2019 Diamond Light Source and Rosalind Franklin Institute
#
# Author: James Parkhurst
#
# This code is distributed under the GPLv3 license, a copy of
# which is included in the root directory of this package.
#
import argparse
import logging
import numpy
import time
import elfantasma.io
import elfantasma.command_line
import elfantasma.config
import elfantasma.sample

# Get the logger
logger = logging.getLogger(__name__)


def exit_wave():
    """
    Simulate the exit wave from the sample

    """

    # Get the start time
    start_time = time.time()

    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="Simulate the exit wave from the sample"
    )

    # Add some command line arguments
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        dest="config",
        help="The yaml file to configure the simulation",
    )
    parser.add_argument(
        "-d",
        "--device",
        choices=["cpu", "gpu"],
        default=None,
        dest="device",
        help="Choose the device to use",
    )
    parser.add_argument(
        "--cluster.max_workers",
        type=int,
        default=None,
        dest="cluster_max_workers",
        help="The maximum number of worker processes",
    )
    parser.add_argument(
        "--cluster.method",
        type=str,
        choices=["sge"],
        default=None,
        dest="cluster_method",
        help="The cluster method to use",
    )
    parser.add_argument(
        "-s",
        "--sample",
        type=str,
        default="sample.h5",
        dest="sample",
        help="The filename for the sample",
    )
    parser.add_argument(
        "-e",
        "--exit_wave",
        type=str,
        default="exit_wave.h5",
        dest="exit_wave",
        help="The filename for the exit wave",
    )

    # Parse the arguments
    args = parser.parse_args()

    # Configure some basic logging
    elfantasma.command_line.configure_logging()

    # Set the command line args in a dict
    command_line = {}
    if args.device is not None:
        command_line["device"] = args.device
    if args.cluster_max_workers is not None or args.cluster_method is not None:
        command_line["cluster"] = {}
    if args.cluster_max_workers is not None:
        command_line["cluster"]["max_workers"] = args.cluster_max_workers
    if args.cluster_method is not None:
        command_line["cluster"]["method"] = args.cluster_method

    # Load the full configuration
    config = elfantasma.config.load(args.config, command_line)

    # Print some options
    elfantasma.config.show(config)

    # Create the microscope
    microscope = elfantasma.microscope.new(**config["microscope"])

    # Create the sample
    logger.info(f"Loading sample from {args.sample}")
    sample = elfantasma.sample.load(args.sample)

    # Create the scan
    scan = elfantasma.scan.new(**config["scan"])

    # Create the simulation
    simulation = elfantasma.simulation.exit_wave(
        microscope=microscope,
        sample=sample,
        scan=scan,
        device=config["device"],
        simulation=config["simulation"],
        cluster=config["cluster"],
    )

    # Create the writer
    logger.info(f"Opening file: {args.exit_wave}")
    writer = elfantasma.io.new(
        args.exit_wave, shape=simulation.shape, dtype=numpy.complex64
    )

    # Run the simulation
    simulation.run(writer)

    # Write some timing stats
    logger.info("Time taken: %.2f seconds" % (time.time() - start_time))


def optics():
    pass


def image():
    pass
