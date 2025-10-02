# 📈 Crypto Dashboard

Prototype cryptocurrency dashboard that fetches and displays real-time crypto price data and DeFi TVL metrics.

Toggle **on** Live Mode to regularly fetch cryptocurrency prices (currently supports only BTC, ETH, cUSD) in real-time, it is set to **off** by default.

Built as part of the **B2C2 Graduate DeFi Developer assignment**.

-----

## 🚀 Features

### Data Integration

  * **BTC & ETH** prices from CoinGecko
  * **cUSD** price via **Celo blockchain node** (Web3, SortedOracles)
  * **Protocol TVL** from DeFiLlama

### REST API

  * `/prices/{symbol}` – historical price samples
  * `/prices/{symbol}/latest` – latest cached price (live mode only)
  * `/tvl/{protocol}` – current TVL for a protocol
  * `/health` – health check
  * `/prices/{symbol}/fetch` – fetch latest price from coingecko server (static mode only)

### Web Interface

  * **Streamlit** dashboard showing charts & tables

### Architecture

  * **FastAPI** backend with OpenAPI/Swagger docs
  * **Postgres** for historical storage
  * **Redis** for caching latest prices + **WebSocket pub/sub**
  * **WebSocket endpoint** for live price updates

### Deployment

  * Dockerized with `docker-compose`
  * Environment variables stored centrally

-----

## 📂 Repository Structure

```
.
├── backend/
│   ├── app.py                # FastAPI app (endpoints, poller, WebSocket)
│   ├── config.py             # Config/env defaults
│   ├── database.py           # SQLAlchemy async setup
│   ├── models/price_model.py # SQLAlchemy Price model
│   ├── services/services.py  # External integrations (CoinGecko, DeFiLlama, cUSD via Web3)
│   └── requirements.txt      # Backend dependencies
├── docker-compose.yml        # Orchestration (backend, frontend, postgres, redis)
├── Dockerfile                # Backend container
├── streamlit_app.py          # Streamlit dashboard (current UI)
└── README.md
```

-----

## 🛠️ Setup Instructions

### 1\. Prerequisites

  * **Docker** + **Docker Compose**
  * **Git**

### 2\. Clone & Run

```bash
git clone https://github.com/Aditya19Joshi01/crypto-webapp.git
cd crypto-webapp

# Build & start all services (backend, frontend, postgres, redis)
docker compose build
docker compose up -d
```

### 3\. Access the App

  * **Backend API docs** → `http://localhost:8000/docs`
  * **Streamlit Dashboard** → `http://localhost:8501`

### 4\. Populate Initial Data (static mode only)

To see data, initially trigger a fetch for each symbol:

```bash
curl -X POST http://localhost:8000/prices/bitcoin/fetch
curl -X POST http://localhost:8000/prices/ethereum/fetch
curl -X POST http://localhost:8000/prices/cusd/fetch
```

-----

## 📡 API Examples

| Request | Description | Example |
| :--- | :--- | :--- |
| Latest BTC price | Fetches latest cached price from Redis | `curl http://localhost:8000/prices/bitcoin/latest` |
| Fetch ETH on-demand | Triggers an immediate fetch and cache update | `curl -X POST http://localhost:8000/prices/ethereum/fetch` |
| TVL of Aave | Fetches current Total Value Locked | `curl http://localhost:8000/tvl/aave` |
| Toggle live mode | Starts/stops the background data poller and WebSocket updates | `curl -X POST -H "Content-Type: application/json" -d '{"live":true}' http://localhost:8000/mode` |

-----

## ⚙️ Tech Stack

  * **Backend:** FastAPI, SQLAlchemy (async), httpx
  * **Frontend:** Streamlit (prototype UI; Next.js React planned)
  * **Database:** Postgres (historical price storage)
  * **Cache:** Redis (latest prices + WebSocket pub/sub)
  * **Blockchain:** `Web3.py` (fetch cUSD price from Celo)
  * **Containerization:** Docker & Docker Compose

-----

## 📌 Key Decisions

  * Used **Docker Compose** to orchestrate backend, frontend, DB, and cache for a streamlined setup.
  * Chose **Streamlit** for quick prototyping of the UI; a **Next.js** frontend will be added later for production quality.
  * Designed the system with **extensibility** (can add new coins/protocols easily).

-----

## 🔮 Next Steps

  * Replace Streamlit with **Next.js React frontend** (already scaffolded).
  * Add **wallet connection** (MetaMask/WalletConnect) for user balances and interaction.
  * Improve DB layer with migrations (**Alembic**) and indexing.
  * Expand test coverage with unit & integration tests.
  * Add monitoring/metrics for performance.

-----

## ✅ Assignment Coverage

  * Fetch BTC, ETH (CoinGecko)
  * Fetch cUSD (**blockchain node, Web3**)
  * Fetch TVL (DeFiLlama)
  * **REST API** with required endpoints + error handling
  * **Web Interface** (Streamlit dashboard)
  * **Dockerized setup**
  * **Extra features:** DB storage, **Redis caching**, **WebSocket live updates**