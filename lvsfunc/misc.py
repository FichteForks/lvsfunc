"""
    Miscellaneous functions and wrappers that didn't really have a place in any other submodules.
"""
from functools import partial
from typing import List, Optional, Tuple, Union

import vapoursynth as vs
from vsutil import get_depth, is_image

from . import util

core = vs.core


def source(file: str, ref: Optional[vs.VideoNode] = None,
           force_lsmas: bool = False,
           mpls: bool = False, mpls_playlist: int = 0, mpls_angle: int = 0) -> vs.VideoNode:
    """
    Generic clip import function.
    Automatically determines if ffms2 or L-SMASH should be used to import a clip, but L-SMASH can be forced.
    It also automatically determines if an image has been imported.
    You can set its fps using 'fpsnum' and 'fpsden', or using a reference clip with 'ref'.

    Dependencies:

        * d2vsource (optional: d2v sources)
        * dgdecodenv (optional: dgi sources)
        * mvsfunc (optional: reference clip mode)
        * vapoursynth-readmpls (optional: mpls sources)

    :param file:              Input file
    :param ref:               Use another clip as reference for the clip's format, resolution, and framerate (Default: None)
    :param force_lsmas:       Force files to be imported with L-SMASH (Default: False)
    :param mpls:              Load in a mpls file (Default: False)
    :param mpls_playlist:     Playlist number, which is the number in mpls file name (Default: 0)
    :param mpls_angle:        Angle number to select in the mpls playlist (Default: 0)

    :return:                  Vapoursynth clip representing input file
    """

    # TODO: Consider adding kwargs for additional options,
    #       find a way to NOT have to rely on a million elif's
    if file.startswith('file:///'):
        file = file[8::]

    # Error handling for some file types
    if file.endswith('.mpls') and mpls is False:
        raise ValueError(f"source: 'Please set \"mpls = True\" and give a path to the base Blu-ray directory when trying to load in mpls files'")
    if file.endswith('.vob') or file.endswith('.ts'):
        raise ValueError(f"source: 'Please index VOB and TS files with d2v before importing them'")

    if force_lsmas:
        return core.lsmas.LWLibavSource(file)

    elif mpls:
        mpls = core.mpls.Read(file, mpls_playlist, mpls_angle)
        clip = core.std.Splice([core.lsmas.LWLibavSource(mpls['clip'][i]) for i in range(mpls['count'])])

    elif file.endswith('.d2v'):
        clip = core.d2v.Source(file)
    elif file.endswith('.dgi'):
        clip = core.dgdecodenv.DGSource(file)
    elif is_image(file):
        clip = core.imwri.Read(file)
    else:
        if file.endswith('.m2ts'):
            clip = core.lsmas.LWLibavSource(file)
        else:
            clip = core.ffms2.Source(file)

    if ref:
        try:
            from mvsfunc import GetMatrix
        except ModuleNotFoundError:
            raise ModuleNotFoundError("source: missing dependency 'mvsfunc'")

        clip = core.std.AssumeFPS(clip, fpsnum=ref.fps.numerator, fpsden=ref.fps.denominator)
        clip = core.resize.Bicubic(clip, width=ref.width, height=ref.height, format=ref.format, matrix_s=GetMatrix(ref))
        if is_image(file):
            clip = clip * (ref.num_frames - 1)

    return clip


def replace_ranges(clip_a: vs.VideoNode,
                   clip_b: vs.VideoNode,
                   ranges: List[Union[int, Tuple[int, int]]]) -> vs.VideoNode:
    """
    A replacement for ReplaceFramesSimple that uses ints and tuples rather than a string.
    Frame ranges are inclusive.

    Written by louis.

    :param clip_a:     Original clip
    :param clip_b:     Replacement clip
    :param ranges:     Ranges to replace clip_a (original clip) with clip_b (replacement clip).
                       Integer values in the list indicate single frames,
                       Tuple values indicate inclusive ranges.

    :return:           Clip with ranges from clip_a replaced with clip_b
    """
    out = clip_a
    for r in ranges:
        if type(r) is tuple:
            start, end = r
        else:
            start = r
            end = r
        tmp = clip_b[start:end + 1]
        if start != 0:
            tmp = out[: start] + tmp
        if end < out.num_frames - 1:
            tmp = tmp + out[end + 1:]
        out = tmp
    return out


def edgefixer(clip: vs.VideoNode,
              left: Optional[List[int]] = None, right: Optional[List[int]] = None,
              top: Optional[List[int]] = None, bottom: Optional[List[int]] = None,
              radius: Optional[List[int]] = None,
              full_range: bool = False) -> vs.VideoNode:
    """
    A wrapper for ContinuityFixer (https://github.com/MonoS/VS-ContinuityFixer).

    Fixes the issues with over- and undershoot that it may create when fixing the edges,
    and adds what are in my opinion "more sane" ways of handling the parameters and given values.

    ...If possible, you should be using bbmod instead, though.

    Dependencies: vs-continuityfixer

    :param clip:        Input clip
    :param left:        Number of pixels to fix on the left (Default: None)
    :param right:       Number of pixels to fix on the right (Default: None)
    :param top:         Number of pixels to fix on the top (Default: None)
    :param bottom:      Number of pixels to fix on the bottom (Default: None)
    :param radius:      Radius for edgefixing (Default: None)
    :param full_range:  Does not run the expression over the clip to fix over/undershoot (Default: False)

    :return:            Clip with fixed edges
    """

    if left is None:
        left = 0
    if right is None:
        right = left
    if top is None:
        top = left
    if bottom is None:
        bottom = top

    ef = core.edgefixer.ContinuityFixer(clip, left, top, right, bottom, radius)
    return ef if full_range else core.std.Limiter(ef, 16, [235, 240])


def fix_cr_tint(clip: vs.VideoNode, value: int = 128) -> vs.VideoNode:
    """
    Tries to forcibly fix Crunchyroll's green tint by adding pixel values.

    :param clip:   Input clip
    :param value:  Value added to every pixel (Default: 128)

    :return:       Clip with CR tint fixed
    """
    if get_depth(clip) != 16:
        clip = util.resampler(clip, 16)
    return core.std.Expr(clip, f'x {value} +')


def limit_dark(clip: vs.VideoNode, filtered: vs.VideoNode,
               threshold: float = 0.25, threshold_range: Optional[int] = None) -> vs.VideoNode:
    """
    Replaces frames in a clip with a filtered clip when the frame's darkness exceeds the threshold.
    This way you can run lighter (or heavier) filtering on scenes that are almost entirely dark.

    There is one caveat, however: You can get scenes where every other frame is filtered
    rather than the entire scene. Please do take care to avoid that if possible.

    :param clip:              Input clip
    :param filtered:          Filtered clip
    :param threshold:         Threshold for frame averages to be filtered (Default: 0.25)
    :param threshold_range:   Threshold for a range of frame averages to be filtered (Default: None)

    :return:                  Conditionally filtered clip
    """
    def _diff(n, f, clip, filtered, threshold, threshold_range):
        if threshold_range:
            return filtered if threshold_range <= f.props.PlaneStatsAverage <= threshold else clip
        else:
            return clip if f.props.PlaneStatsAverage > threshold else filtered

    if threshold_range and threshold_range > threshold:
        raise ValueError(f"limit_dark: '\"threshold_range\" ({threshold_range}) must be a lower value than \"threshold\" ({threshold})'")

    avg = core.std.PlaneStats(clip)
    return core.std.FrameEval(clip, partial(_diff, clip=clip, filtered=filtered, threshold=threshold, threshold_range=threshold_range), avg)


def wipe_row(clip: vs.VideoNode, secondary: vs.VideoNode = Optional[None],
             width: int = 1, height: int = 1,
             offset_x: int = 0, offset_y: int = 0,
             width2: Optional[int] = None, height2: Optional[int] = None,
             offset_x2: Optional[int] = None, offset_y2: Optional[int] = None,
             show_mask: bool = False) -> vs.VideoNode:
    """
    Simple function to wipe a row with a blank clip.
    You can also give it a different clip to replace a row with.

    if width2, height2, etc. are given, it will merge the two masks.

    Dependencies: kagefunc

    :param clip:           Input clip
    :param secondary:      Clip to replace wiped rows with (Default: None)
    :param width:          Width of row (Default: 1)
    :param height:         Height of row (Default: 1)
    :param offset_x:       X-offset of row (Default: 0)
    :param offset_y:       Y-offset of row (Default: 0)
    :param width2:         Width of row 2 (Default: None)
    :param height2:        Height of row 2 (Default: None)
    :param offset_x2:      X-offset of row 2 (Default: None)
    :param offset_y2:      Y-offset of row 2 (Default: None)

    :return:               Clip with rows wiped
    """
    try:
        import kagefunc as kgf
    except ModuleNotFoundError:
        raise ModuleNotFoundError("wipe_row: missing dependency 'kagefunc'")

    secondary = secondary or core.std.BlankClip(clip)

    sqmask = kgf.squaremask(clip, width, height, offset_x, offset_y)
    if width2 and height2:
        sqmask2 = kgf.squaremask(clip, width2, height2, offset_x2, offset_y - 1 if offset_y2 is None else offset_y2)
        sqmask = core.std.Expr([sqmask, sqmask2], "x y +")

    if show_mask:
        return sqmask
    return core.std.MaskedMerge(clip, secondary, sqmask)


def load_bookmarks(bookmark_path: str) -> List[int]:
    """
    VSEdit bookmark loader.

    load_bookmarks(os.path.basename(__file__)+".bookmarks")
    will load the VSEdit bookmarks for the current Vapoursynth script.

    :param bookmark_path:  Path to bookmarks file

    :return:               A list of bookmarked frames
    """
    with open(bookmark_path) as f:
        bookmarks = [int(i) for i in f.read().split(", ")]

        if bookmarks[0] != 0:
            bookmarks.insert(0, 0)

    return bookmarks


def frames_since_bookmark(clip: vs.VideoNode, bookmarks: List[int]) -> vs.VideoNode:
    """
    Displays frames since last bookmark to create easily reusable scenefiltering.
    Can be used in tandem with :py:func:`lvsfunc.misc.load_bookmarks` to import VSEdit bookmarks.

    :param clip:        Input clip
    :param bookmarks:   A list of bookmarks

    :return:            Clip with bookmarked frames
    """
    def _frames_since_bookmark(n: int, clip: vs.VideoNode, bookmarks: List[int]) -> vs.VideoNode:
        for i, bookmark in enumerate(bookmarks):
            frames_since = n - bookmark

            if frames_since >= 0 and i + 1 >= len(bookmarks):
                result = frames_since
            elif frames_since >= 0 and n - bookmarks[i + 1] < 0:
                result = frames_since
                break

        return core.text.Text(clip, result)
    return core.std.FrameEval(clip, partial(_frames_since_bookmark, clip=clip, bookmarks=bookmarks))


# TODO: Write function that only masks px of a certain color/threshold of colors.
#       Think the magic wand tool in various image-editing programs.
