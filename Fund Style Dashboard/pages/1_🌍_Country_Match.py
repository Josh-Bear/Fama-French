"""Country Match page (Phase 5) — scatter กองทุน × exposure ประเทศ (MSCI Country 18 ตัว)."""

import streamlit as st

import page_common

st.set_page_config(page_title="Country Match", page_icon="🌍", layout="wide")
page_common.scatter_page("country", "🌍 Country Match")
