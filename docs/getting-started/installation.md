# Installation

This page explains how to install **PhlyGreen**, its dependencies, and the
recommended development environment. The goal is to provide a clean,
reproducible setup that works for both users and contributors.

---

The recommended setup uses **Conda** to isolate dependencies and ensure consistent behavior across systems.

---

## 1. Install Conda (if not already installed)

If you do not already have Conda or Miniconda, install one of the following:

- **Miniconda:** https://docs.conda.io/en/latest/miniconda.html  
- **Anaconda:** https://www.anaconda.com/products/distribution

Verify installation:

```bash
conda --version
```

---

## 2. Create the Conda Environment

PhlyGreen is tested with Python 3.12, so create a dedicated environment:

```bash
conda create -n phlygreen python=3.12
```

Activate it:

```bash
conda activate phlygreen
```

---

## 3. Clone the Repository

```bash
git clone https://github.com/rmalpica/PhlyGreen.git
cd PhlyGreen
```

Be aware that the repository is still private: you need the admin approval first.

---

## 4. Install Python Dependencies

Install required dependencies:

```bash
pip install -r requirements.txt
```

---

## 5. Install PhlyGreen (Editable Mode Recommended)

Install in development / editable mode:

```bash
cd PhlyGreen/trunk
pip install -e .
```

Why -e?

- Links the package to your local directory
- Any code change is immediately reflected
- No need to reinstall after editing or pulling updates
- Recommended for research and development

For a standard installation instead:

```bash
cd PhlyGreen/trunk
pip install .
```

---

## 6. Verify the Installation

```bash
python -c "import PhlyGreen; print('PhlyGreen version:', PhlyGreen.__version__)"
```

---

## 7. Update your local copy when updates are available in the repository

```bash
git pull
```
