from __future__ import annotations

import io
import re
from pathlib import Path

import qrcode
from PIL import Image, ImageOps


TEMPLATE_PATH = Path(__file__).with_name("connection_template.jpg")


def _qr_value(connection: object) -> str:
    """Return the subscription URL when present, otherwise preserve the full value."""
    value = str(connection or "").strip()
    if not value:
        return ""
    match = re.search(r"https?://[^\s<>]+", value)
    return match.group(0).rstrip(".,);]") if match else value


def make_connection_card(connection: object) -> io.BytesIO | None:
    """Create the Alpha Shop card with a scannable QR centered in the white panel."""
    payload = _qr_value(connection)
    if not payload:
        return None

    base = Image.open(TEMPLATE_PATH).convert("RGB")
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # The white framed panel occupies approximately x=270..990, y=235..995.
    # Keep the QR centered in that panel, as requested, with a clean white margin.
    target_size = 385
    qr_img = ImageOps.contain(qr_img, (target_size, target_size), Image.Resampling.LANCZOS)
    x = (base.width - qr_img.width) // 2
    y = 575 - (qr_img.height // 2)
    base.paste(qr_img, (x, y))

    output = io.BytesIO()
    output.name = "alpha_shop_connection_qr.jpg"
    base.save(output, format="JPEG", quality=95, optimize=True)
    output.seek(0)
    return output
