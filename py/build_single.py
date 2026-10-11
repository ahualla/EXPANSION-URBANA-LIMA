
#!/usr/bin/env python3
"""Genera index.html con CSS, JavaScript y datos integrados."""

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_text(relative_path):
    path = ROOT / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Falta el archivo requerido: {relative_path}")
    return path.read_text(encoding="utf-8")


def main():
    html = read_text("template.html")

    replacements = {
        '<link rel="stylesheet" href="css/style.css">':
            "<style>\n" + read_text("css/style.css") + "\n</style>",

        '<script src="data/data.js"></script>':
            "<script>\n" + read_text("data/data.js") + "\n</script>",

        '<script src="js/app.js"></script>':
            "<script>\n" + read_text("js/app.js") + "\n</script>",
    }

    for original, replacement in replacements.items():
        if original not in html:
            raise RuntimeError(
                f"No se encontró en template.html el elemento esperado: "
                f"{original}"
            )
        html = html.replace(original, replacement)

    logo_path = ROOT / "assets" / "logo.png"
    if not logo_path.is_file():
        raise FileNotFoundError("Falta assets/logo.png")

    logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    html = html.replace(
        "assets/logo.png",
        f"data:image/png;base64,{logo}",
    )

    output = ROOT / "index.html"
    output.write_text(html, encoding="utf-8")
    print(f"OK: generado {output}")


if __name__ == "__main__":
    main()
