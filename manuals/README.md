# PhlyGreen manuals

LaTeX manuals of the PhlyGreen subsystems. The PDFs are not kept in the repository: compile
them from the sources as described below.

| Folder | Manual | Main file |
|---|---|---|
| `battery/` | Battery models | `battery_manual.tex` |
| `engine-decks/` | Engine decks and emissions | `engine_decks_manual.tex` |
| `fuel-cell/` | Fuel cell | `fuelcell_manual.tex` |
| `powertrain/` | Powertrain architectures | `powertrain_manual.tex` |
| `tank/` | Liquid-hydrogen tank | `tank_manual.tex` |
| `tms/` | Thermal management | `tms_manual.tex` |

## Requirements

A TeX distribution with `pdflatex` and `latexmk` (TeX Live, MacTeX or MiKTeX). The manuals use
standard packages only (`amsmath`, `siunitx`, `tikz`, `booktabs`, `tabularx`, `listings`,
`hyperref`, ...), all included in a full TeX Live / MacTeX install. The bibliographies are
written inline, so no BibTeX or Biber run is needed.

## Compile one manual

From the manual's folder:

```bash
cd manuals/fuel-cell
latexmk -pdf -outdir=build fuelcell_manual.tex
```

The PDF is written to `build/fuelcell_manual.pdf`. `latexmk` runs `pdflatex` as many times as
needed for the cross-references and the table of contents. The `build/` folders are ignored by
git.

## Compile all manuals

From the repository root:

```bash
for d in manuals/*/; do
  (cd "$d" && latexmk -pdf -interaction=nonstopmode -outdir=build *_manual.tex)
done
```

Each PDF ends up in `manuals/<name>/build/`. To remove the auxiliary files and the PDFs:

```bash
for d in manuals/*/; do (cd "$d" && latexmk -C -outdir=build *_manual.tex); done
```

## Figures and data

The figures (`figures/`) and the numbers they are made from (`data/`) are kept in the
repository, so compiling needs only LaTeX. Regenerate them only after a change of the code.
Each manual has its own scripts in `scripts/` and a "Reproducing the figures" section with
the exact commands and run times. They need the `phlygreen` environment with the package
installed (`pip install -e ./trunk`); the engine-deck checks also need pyCycle and Cantera.
For example:

```bash
cd trunk
python ../manuals/tank/scripts/make_figures.py --recompute   # re-run the designs, then plot
```

After regenerating, recompile the manual and check that the numbers quoted in the text still
match the new `data/` files.
