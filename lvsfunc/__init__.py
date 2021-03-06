"""
    lvsfunc, a collection of VapourSynth functions and wrappers written and/or modified by LightArrowsEXE.

    If you spot any issues, please do not hesitate to send in a Pull Request
    or reach out to me on Discord (LightArrowsEXE#0476)!
"""

from . import aa, comparison, deinterlace, denoise, util, misc, scale

nneedi3_clamp = aa.nneedi3_clamp
tranpose_aa = aa.transpose_aa
upscaled_sraa = aa.upscaled_sraa

compare = comparison.compare
stack_compare = comparison.stack_compare
stack_planes = comparison.stack_planes
tvbd_diff = comparison.tvbd_diff

deblend = deinterlace.deblend
decomb = deinterlace.decomb
dir_deshimmer = deinterlace.dir_deshimmer
dir_unsharp = deinterlace.dir_unsharp

adaptive_mask = denoise.adaptive_mask
detail_mask = denoise.detail_mask
quick_denoise = denoise.quick_denoise

edgefixer = misc.edgefixer
fix_cr_tint = misc.fix_cr_tint
frames_since_bookmark = misc.frames_since_bookmark
limit_dark = misc.limit_dark
load_bookmarks = misc.load_bookmarks
replace_ranges = misc.replace_ranges
source = misc.source
wipe_row = misc.wipe_row

conditional_descale = scale.conditional_descale
smart_descale = scale.smart_descale
smart_reupscale = scale.smart_reupscale
test_descale = scale.test_descale

# Aliases
comp = compare
cond_desc = conditional_descale
qden = quick_denoise
rfs = replace_ranges
scomp = stack_compare
sraa = upscaled_sraa
src = source
