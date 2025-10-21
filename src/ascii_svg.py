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


import multiprocessing
import os
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image
from numba import njit
from tqdm import tqdm


NORMAL_ASCII_CHARS = [' ', '.', ':', ';', ',', '*', 'o', '8', '#', '&', '%', '@', '$', '=', '+', '^']
NUMBA_ASCII_CHARS_CODES = np.array([ord(c) for c in NORMAL_ASCII_CHARS])

@njit
def rgb_to_ascii_indices_numba(arr):
    """Función acelerada con Numba para convertir RGB a una matriz de índices ASCII."""
    # Nota: Numba no puede acceder a las listas de Python, por eso se pasa el array de códigos internamente.
    # Usamos la constante NUMBA_ASCII_CHARS_CODES definida arriba.

    height, width, _ = arr.shape
    ascii_indices = np.empty((height, width), dtype=np.int32)
    n_chars = len(NUMBA_ASCII_CHARS_CODES)

    for y in range(height):
        for x in range(width):
            pixel = arr[y, x]
            # Cálculo de brillo promedio
            brightness = (pixel[0] + pixel[1] + pixel[2]) // 3
            # Mapeo de 0-255 a índice de caracter (0 a n_chars-1)
            index = brightness * n_chars // 256 # Usar 256 para evitar índice fuera de rango con 255
            if index >= n_chars:
                index = n_chars - 1
            ascii_indices[y, x] = index

    return ascii_indices


def get_ascii_matrix(image):
    """Convierte una imagen PIL a una matriz de caracteres ASCII usando la función Numba."""
    arr = np.array(image)
    indices = rgb_to_ascii_indices_numba(arr)
    # Aquí transformamos los índices a los caracteres finales
    ascii_matrix = [[NORMAL_ASCII_CHARS[i] for i in row] for row in indices]
    return ascii_matrix

# Nota: Estas funciones se definen fuera de la clase para que puedan ser 
# llamadas correctamente desde el método estático y el ProcessPoolExecutor
# sin tener que lidiar con la serialización de la clase completa.

def _static_save_svg(ascii_image, file_path, font_size):
    svg = ET.Element('svg', xmlns="http://www.w3.org/2000/svg", version="1.1")
    height = len(ascii_image)
    width = len(ascii_image[0]) if height > 0 else 0

    for y, row in enumerate(ascii_image):
        for x, char in enumerate(row):
            text = ET.SubElement(svg, 'text', {
                'x': str(x * font_size),
                'y': str((y + 1) * font_size),
                'font-family': "Arial",
                'font-size': str(font_size),
                'fill': 'white'
            })
            text.text = char

    svg.attrib['width'] = str(width * font_size)
    svg.attrib['height'] = str(height * font_size)
    svg.attrib['style'] = "background-color:black"

    tree = ET.ElementTree(svg)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)


class ASCIIConverter:
    """Convierte lotes de imágenes a arte ASCII."""

    def __init__(self, ratio, font_path, font_size=10):
        """
        Inicializa el convertidor con parámetros de configuración fijos.

        Args:
            font_path (str): Ruta al archivo de fuente TTF.
            font_size (int): Tamaño de la fuente para la salida gráfica.
            width_ratio (int): Factor de reducción horizontal.
            height_ratio (int): Factor de reducción vertical.
        """
        self.font_path = font_path
        self.font_size = font_size
        self.width_ratio = ratio
        self.height_ratio = ratio
        self.n_workers = multiprocessing.cpu_count()


    # --- MÉTODO CENTRAL DE PROCESAMIENTO (UNITARIO) ---
    @staticmethod
    def _process_single_file_wrapper(file_path, output_dir, width_ratio, height_ratio, font_size):
        """Función estática de ayuda para ser ejecutada por ProcessPoolExecutor."""
        try:
            # 1. Cargar y Redimensionar
            with Image.open(file_path) as tmp:
                tmp = tmp.copy().convert("RGB")
                orig_w, orig_h = tmp.size
                
                new_w = max(1, int(orig_w / width_ratio))
                new_h = max(1, int(orig_h / height_ratio))
                tmp = tmp.resize((new_w, new_h))

            # 2. Convertir a Matriz ASCII (usa la función global get_ascii_matrix)
            ascii_matrix = get_ascii_matrix(tmp)

            # 3. Guardar el resultado (usando las funciones globales de guardado)
            base = os.path.splitext(os.path.basename(file_path))[0]
            out_path = os.path.join(output_dir, base + ".svg")
            _static_save_svg(ascii_matrix, out_path, font_size)

            return (file_path, out_path, None)

        except Exception as e:
            return (file_path, None, str(e))


    # --- MÉTODO PÚBLICO DE LOTE (BATCH) ---
    def convert_batch(self, input_path, output_path):
        """Convierte un lote de imágenes en paralelo."""
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        extensions = [".jpg", ".jpeg", ".png"]
        files = [os.path.join(input_path, f) for f in os.listdir(input_path) 
                 if any(f.lower().endswith(ext) for ext in extensions)]

        if not files:
            print(f"Advertencia: No se encontraron imágenes en '{input_path}'.")
            return

        print(f"Input files detected: {len(files)}")
        print(f"Starting conversion with {self.n_workers} workers")

        results = []
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            futures = [
                executor.submit(
                    ASCIIConverter._process_single_file_wrapper, # Llamamos al método estático
                    f, 
                    output_path, 
                    self.width_ratio, 
                    self.height_ratio, 
                    self.font_size
                )
                for f in files
            ]
            for future in tqdm(futures, total=len(futures), desc="Converting"):
                results.append(future.result())

        correct = sum(1 for _, out, err in results if err is None)
        failed = [(f, out, err) for f, out, err in results if err is not None]

        print(f"Completed. Success: {correct}, Failed: {len(failed)}")
        if failed:
            print("First 5 errors:")
            for f, _, err in failed[:5]:
                print(f"{os.path.basename(f)} -> {err}")

        print("Batch conversion to SVG completed.")
        return results
