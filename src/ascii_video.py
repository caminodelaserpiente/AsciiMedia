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


from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
import shutil
import subprocess

from src.ascii_image import ArtASCII


def convert_svg_to_png_task(args):
    """
    Tarea global para convertir un SVG a PNG en paralelo.
    args: tuple(svg_path: Path, ref_size: tuple[int,int], output_dir: Path, run_cmd: callable)
    """
    svg_path, ref_size, output_dir, run_cmd = args
    art_proc = ArtASCII(ratio=1, font_path="assets/Arial.ttf", font_size=10)
    art_proc.svg_to_png(svg_path, ref_size=ref_size, output_dir=output_dir, run_cmd=run_cmd)


class ASCIIVideo:
    """Clase que convierte videos completos a ASCII usando ArtASCII."""

    def __init__(self, video_path: str, ratio: int, font_path: str = "assets/Arial.ttf", output_dir="out_ascii", run_cmd=None, n_workers=None):
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.run_cmd = run_cmd
        self.art = ArtASCII(ratio=ratio, font_path=font_path)
        self.temp_frames_dir = Path("temp_frames")
        self.temp_svg_dir = Path("temp_svg")
        self.temp_png_dir = Path("temp_output_png")
        self.n_workers = n_workers

    def extract_frames(self):
        """Extrae todos los frames del video usando ffmpeg."""
        self.temp_frames_dir.mkdir(exist_ok=True)
        self.run_cmd([
            "ffmpeg", "-i", str(self.video_path),
            "-vsync", "vfr", "-q:v", "2",
            "-threads", str(self.n_workers),
            str(self.temp_frames_dir / "frame_%09d.jpg")
        ], "Extrayendo frames")

    def convert_frames_to_ascii(self):
        """Convierte todos los frames extraídos a ASCII SVG."""
        self.temp_svg_dir.mkdir(exist_ok=True)
        self.art.convert_batch_to_svg(str(self.temp_frames_dir), str(self.temp_svg_dir))
        print("Proceeding to PNG rendering...")

    def convert_svg_to_png(self, n_workers=None):
        """Convierte los SVG generados a PNG usando ArtASCII.svg_to_png en paralelo."""
        self.temp_png_dir.mkdir(exist_ok=True)
        svg_files = list(self.temp_svg_dir.glob("*.svg"))

        if not svg_files:
            raise RuntimeError("No se encontraron SVGs para convertir a PNG.")

        # Obtener tamaño de referencia solo una vez
        first_frame = next(iter(self.temp_frames_dir.glob("*.jpg")), None)
        if first_frame is None:
            raise RuntimeError("No se encontraron frames para determinar tamaño.")

        from PIL import Image
        with Image.open(first_frame) as img:
            ref_size = img.size  # (w, h)

        # Preparar argumentos para paralelización
        args_list = [(svg, ref_size, self.temp_png_dir, self.run_cmd) for svg in svg_files]

        # Ejecutar en paralelo con función global
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            list(executor.map(convert_svg_to_png_task, args_list))
        print("Proceeding to final video encoding...")

    def generate_final_video(self, framerate=None):
        """Combina los PNG generados en un video final con audio original."""
        self.output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        final_video = self.output_dir / f"{self.video_path.stem}_{timestamp}{self.video_path.suffix}"

        # Obtener framerate dinámico si no se especifica
        if framerate is None:
            framerate = self._get_video_framerate()
            print(f"Detected source framerate: {framerate}")

        self.run_cmd([
            "ffmpeg", "-framerate", str(framerate),
            "-i", str(self.temp_png_dir / "frame_%09d.png"),
            "-i", str(self.video_path),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-map", "0:v", "-map", "1:a?", "-shortest",
            str(final_video)
        ], "Creando video final")

        return final_video 

    def _get_video_framerate(self):
        """Obtiene el framerate original del video (formato literal, ej: '30000/1001')."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate",
            "-of", "default=nw=1:nk=1",
            str(self.video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        rate_str = result.stdout.strip()

        # Validación mínima
        if not rate_str or "/" not in rate_str:
            rate_str = "30/1"  # fallback seguro
        return rate_str

    def clean_up(self):
        """Elimina todos los directorios temporales utilizados en el proceso."""
        shutil.rmtree(self.temp_frames_dir, ignore_errors=True)
        shutil.rmtree(self.temp_svg_dir, ignore_errors=True)
        shutil.rmtree(self.temp_png_dir, ignore_errors=True)
