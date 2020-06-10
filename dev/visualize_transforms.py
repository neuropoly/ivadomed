#!/usr/bin/env python
##############################################################
#
# This script apply a series of transforms to 2D slices extracted from an input image,
#   and save as png the resulting sample after each transform.
#
# Step-by-step:
#   1. load an image (i)
#   2. extract n slices from this image according to the slice orientation defined in c
#   3. for each successive transforms defined in c applies these transforms to the extracted slices
#   and save the visual result in a output folder o: transform0_slice19.png, transform0_transform1_slice19.png etc.
#
# Usage: python dev/visualize_transforms.py -i <input_filename> -c <fname_config> -n <int> -o <output_folder>
#
##############################################################

import os
import argparse
import nibabel as nib
import numpy as np
import random
import json

from ivadomed.loader import utils as imed_loader_utils
from ivadomed import transforms as imed_transforms
from ivadomed import utils as imed_utils
from testing.utils import plot_transformed_sample


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True,
                        help="Input image filename.")
    parser.add_argument("-c", "--config", required=True,
                        help="Config filename.")
    parser.add_argument("-n", "--number", required=False, default=1,
                        help="Number of random slices to visualize.")
    parser.add_argument("-o", "--ofolder", required=False, default="./",
                        help="Output folder.")
    return parser


def run_visualization(args):
    """Run visualization. Main function of this script.

    Args:
         args argparse.ArgumentParser:

    Returns:
        None
    """
    # Get params
    fname_input = args.input
    n_slices = int(args.number)
    with open(args.config, "r") as fhandle:
        context = json.load(fhandle)
    folder_output = args.ofolder
    if not os.path.isdir(folder_output):
        os.makedirs(folder_output)

    # Load image
    input_img = nib.load(fname_input)
    # Reorient as canonical
    input_img = nib.as_closest_canonical(input_img)
    # Get input data
    input_data = input_img.get_fdata(dtype=np.float32)
    # Reorient data
    axis = imed_utils.AXIS_DCT[context["loader_parameters"]["slice_axis"]]
    input_data = imed_loader_utils.orient_img_hwd(input_data, slice_axis=axis)
    # Get zooms
    zooms = imed_loader_utils.orient_shapes_hwd(input_img.header.get_zooms(), slice_axis=axis)
    # Get indexes
    indexes = random.sample(range(0, input_data.shape[2]), n_slices)

    # Get training transforms
    training_transforms, _, _ = imed_transforms.get_subdatasets_transforms(context["transformation"])

    # Compose transforms
    dict_transforms = {}
    stg_transforms = ""
    for transform_name in training_transforms:
        # Update stg_transforms
        stg_transforms += transform_name + "_"

        # Add new transform to Compose
        dict_transforms.update({transform_name: training_transforms[transform_name]})
        composed_transforms = imed_transforms.Compose(dict_transforms)

        # Loop across slices
        for i in indexes:
            data = [input_data[:, :, i]]
            # Apply transformations
            metadata = imed_loader_utils.SampleMetadata({"zooms": zooms, "data_type": "im"})
            stack_im, _ = composed_transforms(sample=data,
                                              metadata=[metadata for _ in range(n_slices)],
                                              data_type="im")

            # Plot before / after transformation
            fname_out = os.path.join(folder_output, stg_transforms+"slice"+str(i)+".png")
            print("Fname out: {}.".format(fname_out))
            print("\t{}".format(dict(metadata)))
            # rescale intensities
            before = imed_transforms.rescale_values_array(data[0], 0.0, 1.0)
            after = imed_transforms.rescale_values_array(stack_im[0], 0.0, 1.0)
            # Plot
            plot_transformed_sample(before,
                                    after,
                                    list_title=["_".join(stg_transforms[:-1].split("_")[:-1]), stg_transforms[:-1]],
                                    fname_out=fname_out,
                                    cmap="gray")

if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()
    run_visualization(args)
