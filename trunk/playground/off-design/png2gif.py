import os
from PIL import Image
import imageio.v2 as imageio  # Use v2 for backward compatibility

# === USER SETTINGS ===
image_folder = 'cma_scatter_frames_2_fidelity_I'           # Folder where PNGs are stored
output_gif = 'cma_evolution.gif'  # Name of output GIF
duration_per_frame = 0.5          # Seconds per frame

# === COLLECT AND SORT IMAGES, EXCLUDE 'CMA_fitness.png' ===
image_files = sorted([
    os.path.join(image_folder, f)
    for f in os.listdir(image_folder)
    if f.endswith('.png') and f != 'CMA_fitness.png'
])

if not image_files:
    print(f"No eligible PNG files found in '{image_folder}'")
    exit()

# === Determine target size from first image ===
first_img = Image.open(image_files[0])
target_size = first_img.size  # (width, height)

# === Load and resize images ===
images = []
for fname in image_files:
    img = Image.open(fname)
    if img.size != target_size:
        img = img.resize(target_size, Image.ANTIALIAS)
    images.append(imageio.imread(fname))  # Read with imageio for GIF

# === Save as GIF ===
imageio.mimsave(output_gif, images, duration=duration_per_frame)
print(f"GIF saved as '{output_gif}' with {len(images)} frames.")