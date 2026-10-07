"""test_page_common.py — kwargs ความกว้างตาราง/กราฟต้องใช้ได้ทั้ง Streamlit รุ่นใหม่และรุ่นเก่า."""

import page_common


def test_new_streamlit_gets_width_stretch():
    def element(data=None, *, width="stretch", use_container_width=None):  # รูปแบบ 1.5x+
        return None
    assert page_common._full_width(element) == {"width": "stretch"}


def test_old_streamlit_gets_use_container_width():
    def dataframe_140(data=None, width=None, height=None, *, use_container_width=False):  # 1.40: width เป็นตัวเลข
        return None

    def plotly_chart_140(figure_or_data, use_container_width=False, *, theme="streamlit", **kwargs):  # 1.40: ไม่มี width
        return None
    assert page_common._full_width(dataframe_140) == {"use_container_width": True}
    assert page_common._full_width(plotly_chart_140) == {"use_container_width": True}


def test_installed_streamlit_accepts_the_chosen_kwargs():
    import inspect
    import streamlit as st
    for element, kwargs in ((st.dataframe, page_common.TABLE_WIDTH), (st.plotly_chart, page_common.CHART_WIDTH)):
        assert set(kwargs) <= set(inspect.signature(element).parameters)
