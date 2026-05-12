from __future__ import annotations

from io import BytesIO

import segno


def qr_svg(data: str, *, scale: int = 5) -> str:
    qr = segno.make(data, error="m")
    buf = BytesIO()
    qr.save(
        buf,
        kind="svg",
        scale=scale,
        dark="#172033",
        light="#ffffff",
        border=2,
        omitsize=True,
        xmldecl=False,
        svgns=True,
    )
    return buf.getvalue().decode("utf-8")
