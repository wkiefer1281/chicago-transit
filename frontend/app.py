# frontend/app.py
import os

import pandas as pd
import streamlit as st
import pydeck as pdk

from frontend.bq_queries import load_cta_trains, load_cta_buses, load_metra, DEFAULT_LIMIT
from frontend.metrics import build_cta_trains_metrics, build_cta_buses_metrics

REFRESH_MS = int(os.getenv("STREAMLIT_REFRESH_MS", "15000"))


def render_metrics(trains_df: pd.DataFrame, buses_df: pd.DataFrame):
    trains_metrics = build_cta_trains_metrics(trains_df)
    buses_metrics = build_cta_buses_metrics(buses_df)

    cols = st.columns(2)
    cols[0].metric("CTA Trains (rows)", f"{trains_metrics['count']}")
    cols[1].metric("CTA Trains Delayed %", f"{trains_metrics['delayed_pct']:.1f}%")
    st.subheader("CTA Trains per Route")
    st.bar_chart(trains_metrics["top_routes"])

    st.subheader("CTA Buses per Route")
    st.bar_chart(buses_metrics["top_routes"])


def render_map(trains_df: pd.DataFrame, buses_df: pd.DataFrame, metra_df: pd.DataFrame, show_trains: bool, show_buses: bool, show_metra: bool):
    layers = []
    view_state = pdk.ViewState(latitude=41.8781, longitude=-87.6298, zoom=10.5, pitch=0)

    if show_trains and not trains_df.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=trains_df,
                get_position=["lon", "lat"],
                get_radius=70,
                get_fill_color=[225, 29, 72, 200],
                pickable=True,
            )
        )
    if show_buses and not buses_df.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=buses_df,
                get_position=["lon", "lat"],
                get_radius=60,
                get_fill_color=[16, 185, 129, 200],
                pickable=True,
            )
        )
    if show_metra and not metra_df.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=metra_df,
                get_position=["lon", "lat"],
                get_radius=80,
                get_fill_color=[96, 165, 250, 200],
                pickable=True,
            )
        )

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_provider="carto",
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={"text": "{route} {destination_station_name}{destination}{stop_name}\nDelayed: {is_delayed}"},
    )

    st.pydeck_chart(deck)


def main():
    st.set_page_config(page_title="Chicago Transit Live", layout="wide")
    st.title("Chicago Transit Live")
    st.caption("Data from BigQuery tables populated by ETL.")

    # Auto-refresh hint via meta tag (works on Streamlit Cloud).
    st.markdown(
        f"<meta http-equiv='refresh' content='{max(5, REFRESH_MS//1000)}'>",
        unsafe_allow_html=True,
    )
    st.info(f"Auto-refresh every {REFRESH_MS/1000:.0f}s. Adjust via STREAMLIT_REFRESH_MS.", icon="⏱️")

    limit = st.sidebar.number_input(
        "Row limit per table", min_value=100, max_value=5000, value=DEFAULT_LIMIT, step=100
    )
    show_trains = st.sidebar.checkbox("Show CTA trains", value=True)
    show_buses = st.sidebar.checkbox("Show CTA buses", value=True)
    show_metra = st.sidebar.checkbox("Show Metra", value=True)

    trains_df = load_cta_trains(limit)
    buses_df = load_cta_buses(limit)
    metra_df = load_metra(limit)

    render_metrics(trains_df, buses_df)
    render_map(trains_df, buses_df, metra_df, show_trains, show_buses, show_metra)

    with st.expander("Raw data (sample)"):
        st.write("CTA Trains", trains_df.head())
        st.write("CTA Buses", buses_df.head())
        st.write("Metra", metra_df.head())


if __name__ == "__main__":
    main()
