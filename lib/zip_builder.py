"""
ZIP archive builders for mapsystem (SPEC §6.2.2, §8.4, §11).

Functions
---------
build_png_zip(df, store_names, radius_km, progress_cb=None)
    -- ZIP of per-store composite PNGs; failing stores are skipped and
       listed in errors.txt (SPEC §11).
"""

import io
import logging
import zipfile

import pandas as pd

from lib.data import filter_facilities
from lib.png_builder import build_png

logger = logging.getLogger(__name__)


def build_png_zip(
    df: pd.DataFrame,
    store_names: list[str],
    radius_km: float,
    progress_cb=None,
) -> bytes:
    """
    Build a ZIP of composite PNG images, one per store (SPEC §6.2.2, §8.4).

    Parameters
    ----------
    df : pd.DataFrame
        Full master DataFrame.
    store_names : list[str]
        List of 店舗名称 values to include.
    radius_km : float
        Search radius in kilometres.
    progress_cb : callable or None
        Optional callback ``progress_cb(done: int, total: int)`` invoked
        after each store is processed.  Intended for Streamlit st.progress
        integration.

    Returns
    -------
    bytes
        ZIP archive contents.  If any stores fail, ``errors.txt`` is
        included with one failing store name per line (SPEC §11).
    """
    buf = io.BytesIO()
    errors: list[str] = []
    total = len(store_names)

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, store_name in enumerate(store_names):
            try:
                srow = df[df["店舗名称"] == store_name].iloc[0]
                fac = filter_facilities(df, store_name, radius_km)
                png = build_png(srow, fac, radius_km)
                zf.writestr(f"{store_name}.png", png)
                logger.info("build_png_zip: added %s.png (%d/%d)", store_name, i + 1, total)
            except Exception as exc:
                logger.warning(
                    "build_png_zip: skipped %s (%d/%d): %s",
                    store_name,
                    i + 1,
                    total,
                    exc,
                )
                errors.append(store_name)

            if progress_cb is not None:
                progress_cb(i + 1, total)

        if errors:
            zf.writestr("errors.txt", "\n".join(errors))

    buf.seek(0)
    return buf.getvalue()

