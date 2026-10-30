import os

# Must be set before pytest-qt creates a QApplication; there is no display here.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from napari_julich_surfer._atlas import atlas_from_labels


@pytest.fixture
def synthetic_atlas():
    """30³ volume with one grey-matter region spanning the midline and one WM tract."""
    zz, yy, xx = np.mgrid[:30, :30, :30]
    data = np.zeros((30, 30, 30), dtype=np.int16)
    left = (zz - 15) ** 2 + (yy - 15) ** 2 + (xx - 7) ** 2 <= 36
    right = (zz - 15) ** 2 + (yy - 15) ** 2 + (xx - 23) ** 2 <= 36
    data[left | right] = 3  # single GM label covering both hemispheres
    data[(zz - 8) ** 2 + (yy - 8) ** 2 <= 25] = 7  # WM tract crossing the midline
    return atlas_from_labels(
        data,
        (2.0, 2.0, 2.0),
        {3: "GM Test area TP", 7: "WM Test tract"},
        midline_x=15.0,
        name="synthetic",
    )
