"""Page « FAQ »."""

import streamlit as st

from content import CONTENT

faq = CONTENT["faq"]
st.title(faq["title"])
for group in faq["groups"]:
    st.subheader(group["heading"])
    for item in group["questions"]:
        with st.expander(item["q"]):
            for paragraph in item["a"]:
                st.write(paragraph)
