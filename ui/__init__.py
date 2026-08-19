"""ui package: Streamlit-facing helpers for Phase 4 (data access, components, styling).

Nothing in here touches the recommendation algorithm or writes to
MongoDB — it only reads through the existing backend
(database.mongo_client, recommender.recommend) and shapes/display data
for the Streamlit app defined in streamlit_app.py.
"""
