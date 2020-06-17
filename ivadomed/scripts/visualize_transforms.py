#!/usr/bin/env python

import os
import argparse
import nibabel as nib
import numpy as np
import random
import json

from ivadomed.loader import utils as imed_loader_utils
from ivadomed import transforms as imed_transforms
from ivadomed import utils as imed_utils


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
    parser.add_argument("-r", "--roi", required=False,
                        help="ROI filename. Only required if ROICrop is part of the transformations.")
    return parser


def get_data(fname_in, axis):
    """Get data from fname along an axis.

    Args:
         fname_in string: image fname
         axis int:

    Returns:
        nibabel, np.array
    """
    # Load image
    input_img = nib.load(fname_in)
    # Reorient as canonical
    input_img = nib.as_closest_canonical(input_img)
    # Get input data
    input_data = input_img.get_fdata(dtype=np.float32)
    # Reorient data
    input_data = imed_loader_utils.orient_img_hwd(input_data, slice_axis=axis)
    return input_img, input_data


def run_visualization(fname_input, fname_config, n_slices, folder_output, fname_roi):
    """Utility function to visualize Data Augmentation transformations.

    Data augmentation is a key part of the Deep Learning training scheme. This script aims at facilitating the
    fine-tuning of data augmentation parameters. To do so, this script provides a step-by-step visualization of the
    transformations that are applied on data.

    This function applies a series of transformations (defined in a configuration file
    ``-c``) to ``-n`` 2D slices randomly extracted from an input image (``-i``), and save as png the resulting sample
    after each transform.

    For example::

        python visualize_transforms.py -i t2s.nii.gz -n 1 -c config.json -r t2s_seg.nii.gz

    Provides a visualization of a series of three transformation on a randomly selected slice:

    .. image:: ../../images/transforms_im.png
        :width: 600px
        :align: center

    And on a binary mask::

        python visualize_transforms.py -i t2s_gmseg.nii.gz -n 1 -c config.json -r t2s_seg.nii.gz

    Gives:

    .. image:: ../../images/transforms_gt.png
        :width: 600px
        :align: center

    Args:
         fname_input (string): Image filename.
         fname_config (string): Configuration file filename.
         n_slices (int): Number of slices randomly extracted.
         folder_output (string): Folder path where the results are saved.
         fname_roi (string): Filename of the region of interest. Only needed if ROICrop is part of the transformations.

    Returns:
        None
    """
    # Load context
    with open(fname_config, "r") as fhandle:
        context = json.load(fhandle)
    # Create output folder
    if not os.path.isdir(folder_output):
        os.makedirs(folder_output)

    # Slice extracted according to below axis
    axis = imed_utils.AXIS_DCT[context["loader_parameters"]["slice_axis"]]
    # Get data
    input_img, input_data = get_data(fname_input, axis)
    # Image or Mask
    is_mask = np.array_equal(input_data, input_data.astype(bool))
    # Get zooms
    zooms = imed_loader_utils.orient_shapes_hwd(input_img.header.get_zooms(), slice_axis=axis)
    # Get indexes
    indexes = random.sample(range(0, input_data.shape[2]), n_slices)

    # Get training transforms
    training_transforms, _, _ = imed_transforms.get_subdatasets_transforms(context["transformation"])

    if "ROICrop" in training_transforms:
        if fname_roi and os.path.isfile(fname_roi):
            roi_img, roi_data = get_data(fname_roi, axis)
        else:
            print("\nPlease provide ROI image (-r) in order to apply ROICrop transformation.")
            exit()

    # Compose transforms
    dict_transforms = {}
    stg_transforms = ""
    for transform_name in training_transforms:
        # We skip NumpyToTensor transform since that s only a change of data type
        if transform_name == "NumpyToTensor":
            continue

        # Update stg_transforms
        stg_transforms += transform_name + "_"

        # Add new transform to Compose
        dict_transforms.update({transform_name: training_transforms[transform_name]})
        composed_transforms = imed_transforms.Compose(dict_transforms)

        # Loop across slices
        for i in indexes:
            data = [input_data[:, :, i]]
            # Init metadata
            metadata = imed_loader_utils.SampleMetadata({"zooms": zooms, "data_type": "gt" if is_mask else "im"})

            # Apply transformations to ROI
            if "ROICrop" in training_transforms and os.path.isfile(fname_roi):
                roi = [roi_data[:, :, i]]
                metadata.__setitem__('data_type', 'roi')
                _, metadata = composed_transforms(sample=roi,
                                                  metadata=[metadata for _ in range(n_slices)],
                                                  data_type="roi")
                metadata = metadata[0]
                metadata.__setitem__('data_type', 'im')

            # Apply transformations to image
            stack_im, _ = composed_transforms(sample=data,
                                              metadata=[metadata for _ in range(n_slices)],
                                              data_type="im")

            # Plot before / after transformation
            fname_out = os.path.join(folder_output, stg_transforms+"slice"+str(i)+".png")
            print("Fname out: {}.".format(fname_out))
            print("\t{}".format(dict(metadata)))
            # rescale intensities
            if len(stg_transforms[:-1].split("_")) == 1:
                before = np.rot90(imed_transforms.rescale_values_array(data[0], 0.0, 1.0))
            else:
                before = after
            after = np.rot90(imed_transforms.rescale_values_array(stack_im[0], 0.0, 1.0))
            # Plot
            imed_utils.plot_transformed_sample(before,
                                               after,
                                               list_title=["\n".join(stg_transforms[:-1].split("_")[:-1]),
                                                           "\n".join(stg_transforms[:-1].split("_"))],
                                               fname_out=fname_out,
                                               cmap="jet" if is_mask else "gray")


if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()
    fname_input = args.input
    fname_config = args.config
    n_slices = int(args.number)
    folder_output = args.ofolder
    fname_roi = args.roi
    # Run script
    run_visualization(fname_input, fname_config, n_slices, folder_output, fname_roi)