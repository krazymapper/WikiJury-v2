"""Page « À propos »."""

import streamlit as st

from content import CONTENT

about = CONTENT["about"]
st.title(about["title"])
st.markdown(f"#### {about['lead']}")
for section in about["sections"]:
    st.subheader(section["heading"])
    for paragraph in section.get("paragraphs", []):
        st.write(paragraph)
    if section.get("items"):
        st.markdown("\n".join(f"- {item}" for item in section["items"]))
st.divider()
cols = st.columns(len(about["links"]))
for col, link in zip(cols, about["links"]):
    col.link_button(link["label"], link["url"], width="stretch")
