"""
    Helper functions for the main functions in the script.
"""
from functools import partial
from typing import Callable

import vapoursynth as vs

core = vs.core


def one_plane(clip: vs.VideoNode) -> bool:
    """
    Returns True if the clip contains only one plane.

    :param clip:    Input clip

    :return:        Boolean representing whether the input has one plane or not
    """
    return clip.format.num_planes == 1


def resampler(clip: vs.VideoNode, bitdepth: int) -> vs.VideoNode:
    """
    A barebones version of fvsfunc's Depth to remove a common dependency.
    All credit for the original script goes to Frechdachs.

    :param clip:    Input clip
    :param bitdepth: Depth to resample to

    :return:        Clip resampled to bitdepth
    """
    clip_cf = clip.format.color_family
    dst_st = vs.INTEGER if bitdepth < 32 else vs.FLOAT
    src_sw = clip.format.subsampling_w
    src_sh = clip.format.subsampling_h

    if clip.format.bits_per_sample == bitdepth:
        return clip

    dither_type = 'error_diffusion' if bitdepth > clip.format.bits_per_sample else 'none'
    form = core.register_format(clip_cf, dst_st, bitdepth, src_sw, src_sh)
    return core.resize.Point(clip, format=form.id, dither_type=dither_type)


def get_scale_filter(kernel: str, **kwargs) -> Callable[..., vs.VideoNode]:
    """
    kagefunc's get_descale_filter, but for the internal resizers.

    :param kernel:     Resize kernel to use. Currently supports "bilinear", "spline16",
                       "spline36", "spline64", "bicubic", and "lanczos"
    :param kwargs:     Parameters to pass to internal resizers. Parameter c and b
                       are automatically bound to filter_param_a and filter_param_b
                       respectively for bicubic and taps is bound to filter_param_a for lanczos

    :return:           Callable scale function
    """
    kernel = kernel.lower()
    filters = {
        "bilinear": lambda **kwargs: core.resize.Bilinear,
        "spline16": lambda **kwargs: core.resize.Spline16,
        "spline36": lambda **kwargs: core.resize.Spline36,
        "spline64": lambda **kwargs: core.resize.Spline64,
        "bicubic": lambda b, c, **kwargs: partial(core.resize.Bicubic, filter_param_a=b, filter_param_b=c),
        "lanczos": lambda taps, **kwargs: partial(core.resize.Lanczos, filter_param_a=taps),
    }
    return filters[kernel](**kwargs)


def quick_resample(clip: vs.VideoNode, function: Callable[..., vs.VideoNode], **func_args) -> vs.VideoNode:
    """
    A function to quickly resample to 16/8 bit and back to the original depth.
    Useful for filters that only work in 16 bit or lower when you're working in float.

    :param clip:      Input clip
    :param function:  Filter to run after resampling
    :param func_args: Arguments for filter

    :return:          Filtered clip in original depth
    """
    try:
        down = resampler(clip, 16)
        filtered = function(down, **func_args)
    except:
        down = resampler(clip, 8)
        filtered = function(down, **func_args)
    return resampler(filtered, clip.format.bits_per_sample)


# TODO: Merge pick_repair and pick_removegrain?
def pick_repair(clip: vs.VideoNode) -> Callable[..., vs.VideoNode]:
    """
    Returns rgvs.Repair if the clip is 16 bit or lower, else rgsf.Repair.
    This is done because rgvs doesn't work with float, but rgsf does for whatever reason.

    Dependencies: rgsf

    :param clip: Input clip

    :return:     Appropriate repair function for input clip's depth
    """
    return core.rgvs.Repair if clip.format.bits_per_sample < 32 else core.rgsf.Repair


def pick_removegrain(clip: vs.VideoNode) -> Callable[..., vs.VideoNode]:
    """
    Returns rgvs.RemoveGrain if the clip is 16 bit or lower, else rgsf.RemoveGrain.
    This is done because rgvs doesn't work with float, but rgsf does for whatever reason.

    Dependencies: rgsf

    :param clip: Input clip

    :return:     Appropriate RemoveGrain function for input clip's depth
    """
    return core.rgvs.RemoveGrain if clip.format.bits_per_sample < 32 else core.rgsf.RemoveGrain
