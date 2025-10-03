import os
import streamlit as st
import requests
import pandas as pd
import altair as alt

st.set_page_config(page_title="Crypto Dashboard (dev)", layout="wide")

st.title("📈 Crypto Dashboard — Development UI (Streamlit)")

# -------------------- BACKEND CONFIG -------------------- #
DEFAULT_BACKEND = os.getenv(
    "BACKEND_URL", "http://backend:8000"
)  # ✅ use docker service by default
backend_url = st.sidebar.text_input("Backend base URL", value=DEFAULT_BACKEND)

# symbol mapping to match backend
SYMBOL_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "cUSD": "cusd",
}

# -------------------- BACKEND MODE TOGGLE -------------------- #
st.sidebar.markdown("---")
st.sidebar.markdown("### Backend Mode")

try:
    mode_resp = requests.get(f"{backend_url}/mode", timeout=5)
    mode_resp.raise_for_status()
    current_mode = mode_resp.json()
    live_mode = current_mode.get("live_mode", False)

    toggle = st.sidebar.checkbox("Enable Live Mode", value=live_mode)
    if toggle != live_mode:
        update_resp = requests.post(
            f"{backend_url}/mode", json={"live": toggle}, timeout=5
        )
        update_resp.raise_for_status()
        st.sidebar.success(f"Live mode set to {toggle}")
except Exception as e:
    st.sidebar.error(f"⚠️ Could not fetch mode: {e}")

# -------------------- QUICK ACTIONS -------------------- #
st.sidebar.markdown("---")
st.sidebar.markdown("### Quick actions")

symbol = st.sidebar.selectbox("Symbol", list(SYMBOL_MAP.keys()))
if st.sidebar.button("Fetch latest price"):
    try:
        resp = requests.post(
            f"{backend_url}/prices/{SYMBOL_MAP[symbol]}/fetch", timeout=10
        )
        resp.raise_for_status()
        st.success("✅ Latest price fetched and saved to DB")
        st.json(resp.json())
    except Exception as e:
        st.error(f"❌ Failed to fetch latest price: {e}")

# -------------------- PRICE EXPLORER -------------------- #
st.markdown("---")
st.header("💹 Interactive Price Explorer")

col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Price Explorer")
    s = st.selectbox("Choose symbol to plot", list(SYMBOL_MAP.keys()), index=0)
    range_days = st.slider("Days to show (if available)", 1, 180, 30)

    st.markdown("#### 📖 What these metrics mean")
    st.info(
        "- **Price (Blue line):** Actual recorded market price in USD.\n"
        "- **7-day Moving Average (Orange line):** Smooths out short-term noise.\n"
        "- **30-day Moving Average (Green line):** Highlights longer-term trends.\n"
        "- **Δ Price Proxy (Bars):** Magnitude of price changes (used here as a simple proxy for trading volume)."
    )

    # Toggle which series to show
    show_price = st.checkbox("Show Price", value=True)
    show_ma7 = st.checkbox("Show 7-day MA", value=True)
    show_ma30 = st.checkbox("Show 30-day MA", value=False)
    show_delta = st.checkbox("Show Δ Price Proxy (bars)", value=False)

    try:
        resp = requests.get(f"{backend_url}/prices/{SYMBOL_MAP[s]}", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data:
            df = pd.DataFrame(data)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(
                    df["timestamp"], errors="coerce", utc=True
                )
                df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

                # filter by days
                cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=range_days)
                df = df[df["timestamp"] >= cutoff]

                if not df.empty:
                    df["MA7"] = df["price"].rolling(window=7, min_periods=1).mean()
                    df["MA30"] = df["price"].rolling(window=30, min_periods=1).mean()
                    df["delta"] = df["price"].diff().fillna(0).abs()

                    # dynamic y-axis range (with padding)
                    y_min = float(df["price"].min() * 0.98)
                    y_max = float(df["price"].max() * 1.02)

                    charts = []
                    if show_price:
                        charts.append(
                            alt.Chart(df)
                            .mark_line(color="#1f77b4")
                            .encode(
                                x="timestamp:T",
                                y=alt.Y(
                                    "price:Q",
                                    title="Price (USD)",
                                    scale=alt.Scale(domain=[y_min, y_max]),
                                ),
                                tooltip=["timestamp:T", "price:Q"],
                            )
                        )
                    if show_ma7:
                        charts.append(
                            alt.Chart(df)
                            .mark_line(color="orange")
                            .encode(
                                x="timestamp:T",
                                y=alt.Y(
                                    "MA7:Q",
                                    title="Price (USD)",
                                    scale=alt.Scale(domain=[y_min, y_max]),
                                ),
                                tooltip=["timestamp:T", "MA7:Q"],
                            )
                        )
                    if show_ma30:
                        charts.append(
                            alt.Chart(df)
                            .mark_line(color="green")
                            .encode(
                                x="timestamp:T",
                                y=alt.Y(
                                    "MA30:Q",
                                    title="Price (USD)",
                                    scale=alt.Scale(domain=[y_min, y_max]),
                                ),
                                tooltip=["timestamp:T", "MA30:Q"],
                            )
                        )
                    if show_delta:
                        charts.append(
                            alt.Chart(df)
                            .mark_bar(opacity=0.3)
                            .encode(
                                x="timestamp:T",
                                y=alt.Y("delta:Q", title="Δ Price (proxy)"),
                                tooltip=["timestamp:T", "delta:Q"],
                            )
                        )

                    if charts:
                        combined_chart = alt.layer(*charts).resolve_scale(
                            y="independent"
                        )
                        st.altair_chart(combined_chart, use_container_width=True)
                    else:
                        st.warning("No series selected — enable at least one above.")

                    st.subheader("📋 Latest data snapshot")
                    st.dataframe(df.tail(20))
                else:
                    st.warning("No data in this date range.")
            else:
                st.write(df)
        else:
            st.info("No data available — fetch latest to populate DB.")
    except Exception as e:
        st.error(f"❌ Error loading data: {e}")

# -------------------- TVL EXPLORER -------------------- #
with col2:
    st.subheader("TVL Explorer")
    protocol = st.text_input("Protocol name (DeFiLlama)", value="aave")
    if st.button("Fetch TVL"):
        try:
            resp = requests.get(f"{backend_url}/tvl/{protocol}", timeout=10)
            resp.raise_for_status()
            st.json(resp.json())
        except Exception as e:
            st.error(f"❌ Failed to fetch TVL: {e}")

# -------------------- FOOTER -------------------- #
st.markdown("---")
st.caption(
    "⚠️ Dev UI — add authentication, caching, and a production-grade frontend for real deployment."
)
