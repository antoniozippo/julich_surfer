# Jülich 3D Brain Surfer for napari

A brain-surfer style navigator for the **Jülich-Brain (Juelich) atlas** inside
[napari](https://napari.org). Tick one or more cytoarchitectonic parcels in a
searchable list and they light up as coloured 3-D surfaces in the viewer, while the
2-D slice view dims everything you did not select.

## Quick start

```bash
# from this directory
uv sync --extra qt
uv run julich-surfer          # or: uv run python -m napari_julich_surfer
```

Requires Python ≥ 3.10, napari ≥ 0.5 and a Qt binding (the `qt` extra installs PyQt6).
Developed and tested against napari 0.9.2 and nilearn 0.14.1.

With pip:

```bash
pip install -e ".[qt]"
julich-surfer
```

The atlas is downloaded once on first launch (a ~5 MB archive from the FSL data mirror
via `nilearn`, cached in `~/nilearn_data`), so the first window can take a few seconds
to appear. Subsequent launches are offline.

### macOS app

To use it as a double-clickable application instead of a terminal command:

```bash
uv sync --extra qt --extra macos
packaging/build_app.sh
open "dist/Julich 3D Brain Surfer.app"
```

`build_app.sh` renders the icon from the atlas and freezes everything with PyInstaller
into `dist/Julich 3D Brain Surfer.app` (arm64, ~270 MB, ad-hoc signed). The bundle
carries its own Python and needs no virtualenv at run time. It accepts the same flags
as the CLI, e.g. `open -a "$PWD/dist/Julich 3D Brain Surfer.app" --args --legacy-names`,
and you can drag it into `/Applications`. Re-run the script after changing the code.

Two app-specific details: the first launch still downloads the atlas as described above,
and crashes are appended to `~/Library/Logs/JulichBrainSurfer.log` because a windowed
app has nowhere to print. The bundle is ad-hoc signed but not notarized, so copying it
to another Mac may require right-click → Open the first time.

### Windows app

PyInstaller cannot cross-compile, so the `.exe` has to be produced on Windows itself.
On a 64-bit Windows 10/11 machine with Python 3.10+ on `PATH`, double-click
`packaging\build_windows.bat` (or run it from `cmd`):

```bat
packaging\build_windows.bat
```

It creates `.venv`, installs the `qt` and `windows` extras, renders the icon if needed
and freezes the app into `dist\Julich 3D Brain Surfer\Julich 3D Brain Surfer.exe`
(~300 MB folder, the Windows counterpart of the `.app`). Double-click the `.exe`; zip
the whole folder to move it to another PC, where it needs no Python or virtualenv. It
takes the same flags as the CLI (`"Julich 3D Brain Surfer.exe" --legacy-names`) and
crashes go to `%LOCALAPPDATA%\JulichBrainSurfer\JulichBrainSurfer.log`, since a
windowed build has no console. The executable is unsigned, so SmartScreen may ask for
*More info → Run anyway* the first time.

## Using it

The launcher opens napari in 3-D with the surfer docked on the right. The plugin is
also registered as **Plugins → Jülich 3D Brain Surfer** if you prefer to open an
existing napari session:

1. **Filter** the list by typing part of a name (`BA4p`, `V1`, `hIP1`, `fascicle`) or
   narrow it with the grey/white-matter and left/right selectors.
2. **Tick parcels.** Each one becomes its own surface layer, so you can still tweak or
   hide it in napari's layer list. Double-clicking an entry selects it and flies the
   camera there. Names follow Julich-Brain v3.1 (see below); regions that the v3.1
   atlas subdivides further are marked `· N areas`, and FSL-only labels `· not in v3.1`.
3. **Focus** refits the camera to the ticked parcels; **Reset view** returns to the
   whole brain. **3-D view** toggles between the surface navigator and the slice view,
   where the selected parcels are painted bright against a dim atlas. (The slice layer
   is hidden in 3-D so it cannot fog the surfaces; tick it back on in the layer list if
   you want it.)
4. **Surface detail** trades mesh density for speed (`Fast` is instant, `Fine` is
   dense); **Brain** fades or hides the whole-brain shell (it draws without depth
   testing, so it never swallows the parcels inside it), **Parcels** sets the
   highlight opacity, and **Region names** labels the selection.

## Which atlas is this?

`nilearn.datasets.fetch_atlas_juelich` distributes the Jülich histological atlas as
packaged by FSL: maximum-probability maps of 62 grey-matter and white-matter regions in
MNI152 (Amunts, Zilles and colleagues; the SPM Anatomy Toolbox maps). Variants:

| `--atlas` | meaning |
| --- | --- |
| `maxprob-thr25-1mm` (default) | voxels with ≥25 % probability, 1 mm |
| `maxprob-thr50-1mm` | more conservative, 1 mm |
| `maxprob-thr0-1mm` | full coverage, noisy edges |
| `*-2mm` | half-resolution and faster |

That edition is **symmetric**: one label id covers both hemispheres. The surfer splits
grey-matter regions at the midsagittal plane (MNI x = 0) into explicit left and right
parcels, so you can highlight one hemisphere alone. White-matter tracts are kept
bilateral because they cross the midline by nature. Pass `--keep-sides-together` (or
`split_hemispheres=False`) for the unmodified region list.

### Nomenclature

The FSL edition uses 2010-era Anatomy-Toolbox strings such as `Primary motor cortex
BA4p` or `Visual cortex V1 BA17`. The surfer relabels every region to its
**Julich-Brain v3.1** name where one exists: 88 of the 114 parcels become exact v3.1
leaf names like `Area 4p (PreCG) left` or `Area hOc1 (V1, 17, CalcS) right`.

Seven legacy regions are coarser than the v3.1 leaf level and are labelled as groups,
with their members in the list and tooltip:

| Legacy region | v3.1 areas it covers |
| --- | --- |
| `Premotor cortex BA6` | 9 areas: `6d1`, `6d2`, `6d3`, `6ma`, `6mp`, `6r1`, `6v1`, `6v2`, `6v3` |
| `Visual cortex V4` | 4 areas: `hOc4d`, `hOc4la`, `hOc4lp`, `hOc4v` |
| `Amygdala centromedial / laterobasal / superficial group` | 3 / 4 / 3 subnuclei (`CM.*`, `LB.*`, `SF.*`) |
| `Hippocampus cornu ammonis` | 3 areas: `CA1`–`CA3` |
| `Hippocampus subiculum` | 4 areas: `Subc.Sub`, `ProS`, `PreS`, `PaS` |

The ten white-matter tracts and the mamillary body have no v3.1 counterpart at all;
they are kept but marked `not in v3.1`. `--legacy-names` restores the original FSL
strings, and searching still accepts them (`BA4p`, `V1`, `hIP3`).

This is a *naming* alignment, not a re-parcellation: the geometry is still the 62
region FSL maximum-probability map, not the 454 leaf regions of v3.1. Load a v3.1
export with `--nifti` if you need the deeper parcels themselves.

### Using the full Jülich-Brain v3.0

Newer EBRAINS releases (157 areas) are not fetchable without an account, so export a
maximum-probability map from EBRAINS/siibra as NIfTI and point the surfer at it:

```bash
julich-surfer --nifti JulichBrain_v3.1_maxprob_MNI152.nii.gz \
              --labels julich_labels.json     # {"1": "Area hOc1 ...", ...}
```

`--labels` accepts a JSON object (`{value: name}`), a JSON list (names in label order,
a leading `"Background"` is tolerated), or a plain text file with one name per line.
From Python, `napari_julich_surfer.atlas_from_nifti(...)` returns the same `Atlas`
object the widget uses.

## Programmatic use

```python
import napari
from napari_julich_surfer import JulichSurferWidget, fetch_juelich

viewer = napari.Viewer()
atlas = fetch_juelich("maxprob-thr25-1mm")
surfer = JulichSurferWidget(viewer, atlas=atlas)
viewer.window.add_dock_widget(surfer, area="right")

left = [p.value for p in atlas.parcels if p.label == "Area 4p (PreCG) left"]
surfer.select(left)          # same as ticking those rows by hand
napari.run()

# atlas = fetch_juelich(v31_names=False) keeps the old FSL labels
```

## How it works

* `_atlas.py` re-orients the NIfTI into display order `(z, y, x)` (RAS, superior up),
  splits symmetric regions, and computes per-parcel volume, centroid and bbox.
* `_nomenclature.py` maps the 62 legacy FSL regions onto exact Julich-Brain v3.1 names,
  records group membership, and flags labels with no v3.1 counterpart.
* `_surfaces.py` extracts one clean isosurface per parcel with marching cubes
  (`step_size`/Gaussian pre-smoothing per detail level), memoised per parcel.
* `_widget.py` keeps the napari layers in sync with the ticked rows: one `Surface`
  per parcel, a translucent whole-atlas shell for context, a `Points` layer holding
  the region names, and a `Labels` layer with a `DirectLabelColormap` for the slices.

Surfaces are in millimetres, so measurements and napari's scale bar are meaningful.

## Tests

```bash
uv sync --extra qt --extra dev
uv run pytest
```

The widget tests drive the real Qt widget against napari's `ViewerModel` with
`QT_QPA_PLATFORM=offscreen`, so they need no display. The network is only used when
the full atlas is fetched; tests build synthetic volumes.

## Caveats

* The FSL maximum-probability map is not a probabilistic atlas: the surfer highlights
  the arg-max assignment, not per-region probability volumes. For probabilistic work,
  load the `Juelich-prob-*` maps with nilearn directly.
* v3.1 naming does not add v3.1 parcels: a group such as `Premotor cortex (Area 6
group)` is one 2010 parcel covering nine v3.1 areas, and areas that exist only in v3.1
(cingulate 24 subdivisions, `Id2`–`Id10`, `Op5`–`Op10`, basal forebrain) are absent.
* Splitting at x = 0 is geometric. Regions that genuinely straddle the midline (some
  midline grey-matter structures) get a left and a right half rather than one parcel.
* 3-D rendering is surface-based, not volume rendering; deep parcels are visible by
  rotating or by switching to the slice view.

## Citations

Amunts K. et al. (2020) *Jülich-Brain: a 3D probabilistic atlas of human brain
cytoarchitecture*, Science. Eickhoff S.B. et al. (2005, 2007) for the SPM Anatomy
Toolbox maps. Data accessed through `nilearn`'s FSL packaging; please also cite FSL.

Licensed under BSD-3-Clause.
