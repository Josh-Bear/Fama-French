"""Sector Match page (Phase 5) — scatter กองทุน × exposure sector (MSCI Sector 10 ตัว)."""

import streamlit as st

import page_common

_SECTOR_LEGEND = ("sector code: CD=consumer disc, CS=staples, EN=energy, FN=financials, "
                  "HC=health care, IN=industrials, IT=info tech, MT=materials, TC=comm services, UT=utilities")

st.set_page_config(page_title="Sector Match", page_icon="🏭", layout="wide")
page_common.scatter_page("sector", "🏭 Sector Match", extra_caption=_SECTOR_LEGEND)
