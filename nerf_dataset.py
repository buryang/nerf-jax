#!/usr/bin/env python3

import os
from pathlib import Path
import json
from io import StringIO

import numpy as np
import yaml
import box
import imageio
import jax
from jax import jit, vmap
import jax.numpy as jnp


def filter_chain(img, options):
    # first, normalize from [0.0, 1.0]
    img = img.astype(jnp.float32) / 255.0

    # next, resize to half-resolution
    if options.downscale != 1:
        factor = options.downscale
        img = jax.image.resize(
            img,
            shape=(img.shape[0] // factor, img.shape[1] // factor, img.shape[2]),
            method=jax.image.ResizeMethod.LINEAR,
            antialias=True,
        )

    if options.white_background:
        img = img[..., :3] * img[..., -1:] + (1.0 - img[..., -1:])

    return img


def loader(data_dir, filter_chain_options, device):
    """
    Loads images from disk into a big numpy array, which will
    later be pmapped onto all devices.
    """
    splits = [entry for entry in data_dir.iterdir() if entry.is_dir()]

    metadata = {
        split: json.load(
            StringIO((data_dir / f"transforms_{split.name}.json").read_text())
        )
        for split in splits
    }

    vmap_filter_chain = vmap(
        lambda imgs: jit(filter_chain, static_argnums=(1,), device=device)(
            imgs, filter_chain_options
        ),
    )

    frame_iterator = lambda f, mdata: np.stack(
        [
            f(frame)
            for idx, frame in enumerate(mdata["frames"])
            if idx % filter_chain_options.skiptest == 0
        ],
        axis=0,
    )

    images = {
        split.name: np.array(
            vmap_filter_chain(
                jnp.array(
                    frame_iterator(
                        lambda frame: imageio.imread(
                            data_dir / f"{frame['file_path']}.png"
                        ),
                        mdata,
                    )
                )
            )
        )
        for split, mdata in metadata.items()
    }

    poses = {
        split.name: frame_iterator(lambda frame: frame["transform_matrix"], mdata)
        for split, mdata in metadata.items()
    }

    return images, poses


@jit
def sampler():
    """
    """
    pass


if __name__ == "__main__":
    from collections import namedtuple

    import cv2

    # example setup with the lego data
    FilterChainOptions = namedtuple(
        "FilterChainOptions", ["skiptest", "downscale", "white_background"]
    )
    example_options = FilterChainOptions(skiptest=1, downscale=2, white_background=True)

    devices = jax.devices("cpu")
    # devices = jax.devices("gpu")

    images, poses = loader(
        Path(".") / "data" / "nerf_synthetic" / "lego",
        example_options,
        devices[0],
    )

    for image in images["test"]:
        cv2.imshow("img", image[:, :, [2, 1, 0]])
        cv2.waitKey(1)

    print(poses)