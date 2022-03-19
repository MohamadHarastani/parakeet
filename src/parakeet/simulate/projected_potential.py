#
# parakeet.simulate.projected_potential.py
#
# Copyright (C) 2019 Diamond Light Source and Rosalind Franklin Institute
#
# Author: James Parkhurst
#
# This code is distributed under the GPLv3 license, a copy of
# which is included in the root directory of this package.
#

import logging
import mrcfile
import numpy as np
import warnings
import parakeet.config
import parakeet.dqe
import parakeet.freeze
import parakeet.futures
import parakeet.inelastic
import parakeet.sample
from parakeet.microscope import Microscope
from parakeet.sample import Sample
from parakeet.scan import Scan
from functools import singledispatch
from math import pi, floor

# Get the logger
logger = logging.getLogger(__name__)

# Try to input MULTEM
try:
    import multem
except ImportError:
    warnings.warn("Could not import MULTEM")


class ProjectedPotentialSimulator(object):
    """
    A class to do the actual simulation

    The simulation is structured this way because the input data to the
    simulation is large enough that it makes an overhead to creating the
    individual processes.

    """

    def __init__(
        self, microscope=None, sample=None, scan=None, simulation=None, device="gpu"
    ):
        self.microscope = microscope
        self.sample = sample
        self.scan = scan
        self.simulation = simulation
        self.device = device

    def __call__(self, index):
        """
        Simulate a single frame

        Args:
            simulation (object): The simulation object
            index (int): The frame number

        Returns:
            tuple: (angle, image)

        """

        # Get the rotation angle
        angle = self.scan.angles[index]
        position = self.scan.positions[index]

        # The field of view
        nx = self.microscope.detector.nx
        ny = self.microscope.detector.ny
        pixel_size = self.microscope.detector.pixel_size
        margin = self.simulation["margin"]
        x_fov = nx * pixel_size
        y_fov = ny * pixel_size
        offset = margin * pixel_size

        # Get the specimen atoms
        logger.info(f"Simulating image {index+1}")

        # Create the sample extractor
        x0 = (-offset, -offset)
        x1 = (x_fov + offset, y_fov + offset)

        # Create the multem system configuration
        system_conf = parakeet.simulate.simulation.create_system_configuration(
            self.device
        )

        # The Z centre
        z_centre = self.sample.centre[2]

        # Create the multem input multislice object
        input_multislice = parakeet.simulate.simulation.create_input_multislice(
            self.microscope,
            self.simulation["slice_thickness"],
            self.simulation["margin"],
            "EWRS",
            z_centre,
        )

        # Set the specimen size
        input_multislice.spec_lx = x_fov + offset * 2
        input_multislice.spec_ly = y_fov + offset * 2
        input_multislice.spec_lz = self.sample.containing_box[1][2]

        # Set the atoms in the input after translating them for the offset
        atoms = self.sample.get_atoms_in_fov(x0, x1)
        logger.info("Simulating with %d atoms" % atoms.data.shape[0])

        # Set atom sigma
        # atoms.data["sigma"] = sigma_B

        if len(atoms.data) > 0:
            coords = atoms.data[["x", "y", "z"]].to_numpy()
            coords = (
                self.scan.poses.orientations[index].apply(coords - self.sample.centre)
                + self.sample.centre
                - self.scan.poses.shifts[index]
            ).astype("float32")
            atoms.data["x"] = coords[:, 0]
            atoms.data["y"] = coords[:, 1]
            atoms.data["z"] = coords[:, 2]

        origin = (0, 0)
        input_multislice.spec_atoms = atoms.translate(
            (offset - origin[0], offset - origin[1], 0)
        ).to_multem()
        logger.info("   Got spec atoms")

        # Get the potential and thickness
        volume_z0 = self.sample.shape_box[0][2]
        volume_z1 = self.sample.shape_box[1][2]
        slice_thickness = self.simulation["slice_thickness"]
        zsize = int(floor((volume_z1 - volume_z0) / slice_thickness))
        potential = mrcfile.new_mmap(
            "projected_potential_%d.mrc" % index,
            shape=(zsize, ny, nx),
            mrc_mode=mrcfile.utils.mode_from_dtype(np.dtype(np.float32)),
            overwrite=True,
        )
        potential.voxel_size = tuple((pixel_size, pixel_size, slice_thickness))

        def callback(z0, z1, V):
            V = np.array(V)
            zc = (z0 + z1) / 2.0
            index = int(floor((zc - volume_z0) / slice_thickness))
            print(
                "Calculating potential for slice: %.2f -> %.2f (index: %d)"
                % (z0, z1, index)
            )
            potential.data[index, :, :] = V[margin:-margin, margin:-margin].T

        # Run the simulation
        multem.compute_projected_potential(system_conf, input_multislice, callback)

        # Compute the image scaled with Poisson noise
        return (index, angle, position, None, None, None)


def projected_potential_internal(
    microscope: Microscope,
    sample: Sample,
    scan: Scan,
    device: str = "gpu",
    simulation: dict = None,
    cluster: dict = None,
):
    """
    Create the simulation

    Args:
        microscope (object); The microscope object
        sample (object): The sample object
        scan (object): The scan object
        device (str): The device to use
        simulation (object): The simulation parameters
        cluster (object): The cluster parameters

    Returns:
        object: The simulation object

    """

    # Create the simulation
    return parakeet.simulate.simulation.Simulation(
        image_size=(
            microscope.detector.nx + 2 * simulation["margin"],
            microscope.detector.ny + 2 * simulation["margin"],
        ),
        pixel_size=microscope.detector.pixel_size,
        scan=scan,
        cluster=cluster,
        simulate_image=ProjectedPotentialSimulator(
            microscope=microscope,
            sample=sample,
            scan=scan,
            simulation=simulation,
            device=device,
        ),
    )


@singledispatch
def projected_potential(
    config_file: str,
    sample_file: str,
    device: str = "gpu",
    cluster_method: str = None,
    cluster_max_workers: int = 1,
):
    """
    Simulate the projected potential from the sample

    """

    # Load the full configuration
    config = parakeet.config.load(config_file)

    # Set the command line args in a dict
    if device is not None:
        config.device = device
    if cluster_max_workers is not None:
        config.cluster.max_workers = cluster_max_workers
    if cluster_method is not None:
        config.cluster.method = cluster_method

    # Print some options
    parakeet.config.show(config)

    # Create the microscope
    microscope = parakeet.microscope.new(**config.microscope.dict())

    # Create the sample
    logger.info(f"Loading sample from {sample_file}")
    sample = parakeet.sample.load(sample_file)

    # Create the scan
    if config.scan.step_pos == "auto":
        radius = sample.shape_radius
        config.scan.step_pos = config.scan.step_angle * radius * pi / 180.0
    scan = parakeet.scan.new(**config.scan.dict())

    # Create the simulation
    simulation = projected_potential_internal(
        microscope=microscope,
        sample=sample,
        scan=scan,
        device=config.device,
        simulation=config.simulation.dict(),
        cluster=config.cluster.dict(),
    )

    # Run the simulation
    simulation.run()


# Register function for single dispatch
projected_potential.register(projected_potential_internal)
