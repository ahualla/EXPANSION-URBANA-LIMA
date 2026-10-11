#!/usr/bin/env python3
"""Genera index.html autocontenido (CSS, JS, datos y logo incluidos) a partir de template.html."""
import base64
from pathlib import Path
R = Path(__file__).resolve().parent.parent; rd = lambda p: (R/p).read_text(encoding="utf-8")
h = rd("template.html")
h = h.replace('<link rel="stylesheet" href="css/style.css">', "<style>"+rd("css/style.css")+"</style>")
h = h.replace('<script src="data/data.js"></script>', "<script>"+rd("data/data.js")+"</script>")
h = h.replace('<script src="js/app.js"></script>', "<script>"+rd("js/app.js")+"</script>")
h = h.replace("assets/logo.png", "data:image/png;base64," + base64.b64encode((R/"assets/logo.png").read_bytes()).decode())
(R/"index.html").write_text(h, encoding="utf-8"); print("OK -> index.html")
