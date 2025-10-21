# Copyright (C) Daniel A. L.
# Repository: https://github.com/caminodelaserpiente/AsciiMedia

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import shutil
from pathlib import Path

from src.ascii_svg import ASCIIConverter


class ArtASCII:
    """Clase que maneja la conversión completa de imágenes a ASCII y su exportación a PNG."""

    def __init__(self, ratio: int, font_path: str = "assets/Arial.ttf", font_size: int = 10, n_workers=None):
        self.ratio = ratio
        self.font_path = font_path
        self.font_size = font_size
        self.n_workers = n_workers
        self.converter = ASCIIConverter(ratio=self.ratio, font_path=self.font_path, font_size=self.font_size)

    def convert_image_to_svg(self, image_path: str, output_dir: str):
        """Convierte una sola imagen a SVG usando ASCIIConverter."""
        return ASCIIConverter._process_single_file_wrapper(
            file_path=image_path,
            output_dir=output_dir,
            width_ratio=self.ratio,
            height_ratio=self.ratio,
            font_size=self.font_size
        )

    def convert_batch_to_svg(self, input_dir: str, output_dir: str):
        """Convierte un lote de imágenes a SVG en paralelo."""
        return self.converter.convert_batch(input_dir, output_dir)

    def svg_to_png(self, svg_path: Path, ref_size: tuple[int,int]=None, output_dir: Path = None, default_size=(550,978), run_cmd=None):
        """Convierte un SVG a PNG usando rsvg-convert y convert (ImageMagick). 
        ref_size: (width, height) fijo opcional para videos.
        """
        if run_cmd is None:
            raise ValueError("Se requiere la función run_cmd para ejecutar comandos externos.")

        base = svg_path.stem
        output_dir = Path(output_dir) if output_dir else Path(".")
        output_dir.mkdir(exist_ok=True)
        out_png = output_dir / f"{base}.png"

        # Determinar tamaño final
        if ref_size:
            w, h = ref_size
        elif ref_image_path and Path(ref_image_path).exists():
            from PIL import Image
            with Image.open(ref_image_path) as img:
                w, h = img.size
        else:
            w, h = default_size

        temp_png = output_dir / f"{base}_temp.png"
        run_cmd(["rsvg-convert", "-w", str(w), "-h", str(h), str(svg_path), "-o", str(temp_png)],
                f"Convirtiendo {svg_path.name} a PNG temporal")
        run_cmd(["convert", str(temp_png), "-background", "black", "-flatten", "-extent", f"{w}x{h}", str(out_png)],
                f"Generando PNG final {out_png.name}")
        temp_png.unlink(missing_ok=True)
        return out_png

# ==========================
# Función global para multiprocesamiento
# ==========================
def _convert_svg_to_png_task(args):
    svg_file, input_dir, output_dir, font_size, ratio, run_cmd = args
    from pathlib import Path
    input_dir = Path(input_dir)

    # Obtener imagen de referencia
    ref_image = input_dir / f"{svg_file.stem}.png"  # default
    for ext in [".jpg", ".jpeg", ".png"]:
        tmp = input_dir / f"{svg_file.stem}{ext}"
        if tmp.exists():
            ref_image = tmp
            break

    from PIL import Image
    with Image.open(ref_image) as img:
        ref_size = img.size  # tamaño original de la imagen

    art_proc = ArtASCII(ratio=ratio, font_path="assets/Arial.ttf", font_size=font_size)
    art_proc.svg_to_png(svg_file, ref_size=ref_size, output_dir=output_dir, run_cmd=run_cmd)


# ==========================
# Método principal para pipeline completo de imágenes
# ==========================
def convert_images_to_png(input_dir: str, output_dir: str, run_cmd, ratio: int, font_size: int = 10, n_workers=None):
    """
    Pipeline completo de imágenes: SVG temporal → PNG final → limpieza.

    Args:
        input_dir: Carpeta con imágenes originales (.jpg/.png).
        output_dir: Carpeta donde se guardarán los PNG finales.
        run_cmd: Función para ejecutar comandos externos (rsvg-convert / convert).
        ratio: Ratio de resolución ASCII.
        font_size: Tamaño de fuente para SVG.
        n_workers: Número de procesos en paralelo.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    temp_svg_dir = Path("temp_svg")
    temp_svg_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    # 1️⃣ Convertir imágenes a SVG
    art_proc = ArtASCII(ratio=ratio, font_path="assets/Arial.ttf", font_size=font_size, n_workers=n_workers)
    art_proc.convert_batch_to_svg(str(input_dir), str(temp_svg_dir))
    print("Proceeding to PNG rendering...")

    # 2️⃣ Convertir SVG a PNG en paralelo
    svg_files = list(temp_svg_dir.glob("*.svg"))
    if not svg_files:
        raise RuntimeError("No SVGs generados. Revisa la conversión.")

    args_list = [(svg, str(input_dir), str(output_dir), font_size, ratio, run_cmd) for svg in svg_files]

    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        list(executor.map(_convert_svg_to_png_task, args_list))

    # 3️⃣ Limpiar temporales
    shutil.rmtree(temp_svg_dir, ignore_errors=True)
