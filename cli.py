import argparse
import multiprocessing
import subprocess
import sys
import time
from pathlib import Path

from src.ascii_image import convert_images_to_png
from src.ascii_video import ASCIIVideo


asrt = """
::::: ###::::: ######::: ######:: ######: ######::::
:::: ## ##::: ##... ##: ##... ##::: ##::::: ##::::::
::: ##:. ##:: ##:::..:: ##:::..:::: ##::::: ##::::::
:: ##:::. ##:. ######:: ##::::::::: ##::::: ##::::::
:: #########::..... ##: ##::::::::: ##::::: ##::::::
:: ##.... ##: ##::: ##: ##::: ##::: ##::::: ##::::::
:: ##:::: ##:. ######::. ######:: ######: ######::::
:::..::::..::::.....:::::.....::::.....:::.....:::::
: ##:::::##: ########: ########:: ######:::: ###::::
: ###:::###: ##.....:: ##.... ##::  ##::::: ## ##:::
: ####:####: ##::::::: ##:::: ##::: ##:::: ##:. ##::
: ## ### ##: ######::: ##:::: ##::: ##::: ##:::. ##:
: ##. #: ##: ##...:::: ##:::: ##::: ##::: #########:
: ##:.:: ##: ##::::::: ##:::: ##::: ##::: ##.... ##:
: ##:::: ##: ########: ########:: ######: ##:::: ##:
::..::::..:::.......:::.......::::.....:::..::::..::
"""

def run_cmd(cmd: list[str], desc: str):
    """Ejecuta un comando y muestra errores de forma clara."""
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        print(f"[Error] Comando no encontrado: {cmd[0]}. Asegúrate de que esté instalado.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[Error] Falló: {desc}")
        print(f"Comando: {' '.join(cmd)}")
        if e.stderr:
            print(f"Detalle:\n{e.stderr.strip()}")
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            f"{asrt}"
            "Description: Transform images or videos into ASCII art.\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        help="Path to folder with source images (.jpg, .png). Required if --video is not used."
    )
    parser.add_argument(
        "-v", "--video",
        type=str,
        help="Path to a video file to convert into ASCII art. Required if input_dir is not provided."
    )
    parser.add_argument(
        "-r", "--ratio",
        type=int,
        required=True,
        help="Set the ASCII resolution ratio (lower = finer detail)."
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="out_ascii",
        help="Output directory for ASCII files. Default: %(default)s"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.video and args.input_dir:
        print("Error: Use either --video or an image directory, not both.")
        sys.exit(1)
    if not args.video and not args.input_dir:
        print("Error: Specify an image directory or use --video.")
        sys.exit(1)

    input_path = Path(args.input_dir) if args.input_dir else None
    video_path = Path(args.video) if args.video else None
    output_dir = Path(args.output_dir)
    n_workers = multiprocessing.cpu_count()
    start_time = time.perf_counter()  # Inicio del cronómetro
    try:
        if video_path:
            video_proc = ASCIIVideo(video_path=str(video_path), 
                                    ratio=args.ratio, 
                                    output_dir=str(output_dir), 
                                    run_cmd=run_cmd,
                                    n_workers=n_workers
                                    )
            video_proc.extract_frames()
            video_proc.convert_frames_to_ascii()
            video_proc.convert_svg_to_png()
            final_video = video_proc.generate_final_video()
            print(f"✅ ASCII video successfully generated: {final_video}")
            video_proc.clean_up()
        else:
            convert_images_to_png(
                input_dir=str(input_path),
                output_dir=str(output_dir),
                run_cmd=run_cmd,
                ratio=args.ratio,
                n_workers=n_workers
            )
            print(f"✅ ASCII image completed. Files stored in '{output_dir}'")

    finally:
        end_time = time.perf_counter()
        elapsed = end_time - start_time
        minutes, seconds = divmod(elapsed, 60)
        print(f"\n⏱️  Total processing time: {int(minutes)} min {seconds:.1f} sec")

if __name__ == "__main__":
    main()
