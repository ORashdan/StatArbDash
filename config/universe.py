"""
Trading universe definition with baskets of correlated symbols.
All symbols must be in CCXT format (e.g., "ARB/USDT" not "ARBUSD").
"""

BASKETS: dict[str, list[str]] = {

    # EVM / Ethereum-family (same stack, similar drivers)
    "eth_l1_core": ["ETHUSD", "ETCUSD", "BTCUSD"],
    "eth_l2_scaling": ["ARBUSD", "OPUSD", "LRCUSD", "IMXUSD", "BTCUSD"],

    # DeFi protocol design (same business model)
    "amm_dex_core": ["UNIUSD", "SUSHIUSD", "CRVUSD", "ZRXUSD", "BTCUSD"],
    "defi_core_governance": ["AAVEUSD", "MKRUSD", "LDOUSD", "YFIUSD", "LINAUSD", "BTCUSD"],
    "perps_derivatives": ["DYDXUSD", "GMXUSD", "HYPEUSD", "INJUSD", "BTCUSD"],

    # Data infra
    "oracles": ["LINKUSD", "BANDUSD", "PYTHUSD", "BTCUSD"],
    "web3_infra_services": ["ANKRUSD", "BICOUSD", "CVCUSD", "BTCUSD"],
    "content_social_attention": ["BATUSD", "MASKUSD", "COSUSD", "BTCUSD"],

    # Gaming / NFT / metaverse
    "gaming_tokens": ["AXSUSD", "GALAUSD", "ENJUSD", "BTCUSD"],
    "nft_metaverse_communities": ["APEUSD", "MAGICUSD", "AGLDUSD", "PENGUUSD", "BTCUSD"],

    # Solana meme cluster (same chain + similar flow)
    "solana_memes": ["1000BONKUSD", "WIFUSD", "POPCATUSD", "MELANIAUSD", "ACTUSD", "BTCUSD"],

    # Dog-meme cluster (same narrative)
    "dog_memes_large": ["DOGEUSD", "1000SHIBUSD", "1000FLOKIUSD", "BTCUSD"],
    "misc_memes": ["1000PEPEUSD", "1000CHEEMSUSD", "BRETTUSD", "MEMEUSD", "BTCUSD"],

    # Fan tokens (same platform style / demand)
    "fan_tokens": ["CHZUSD", "ASRUSD", "BTCUSD"],

    # Bitcoin ecosystem
    "btc_core_and_forks": ["BTCUSD", "BCHUSD", "BSVUSD", "BCHBTC"],
    "btc_adjacent_protocols": ["STXUSD", "ORDIUSD", "BTCUSD"],
    "utxo_payments_privacy": ["LTCUSD", "DASHUSD", "ZECUSD", "BTCUSD"],

    # Interop / modular thesis
    "interop_modular": ["ATOMUSD", "DOTUSD", "TIAUSD", "QNTUSD", "BTCUSD"],
    "cosmos_ecosystem_builders": ["SEIUSD", "AKTUSD", "RUNEUSD", "BTCUSD"],

    # L1 “style” baskets (similar market regime / positioning)
    "evm_compatible_l1s": ["BNBUSD", "AVAXUSD", "FTMUSD", "BTCUSD"],
    "new_gen_l1s": ["SOLUSD", "SUIUSD", "APTUSD", "BTCUSD"],
    "legacy_alt_l1s": ["ADAUSD", "ALGOUSD", "XTZUSD", "BTCUSD"],
    "enterprise_dlt_supplychain": ["HBARUSD", "VETUSD", "BTCUSD"],
    "neo_ecosystem": ["NEOUSD", "GASUSD", "FLMUSD", "BTCUSD"],
    "other_l1s_mixed": ["NEARUSD", "EGLDUSD", "ICPUSD", "BTCUSD"],
    "pow_alt_l1s": ["KASUSD", "CFXUSD", "BTCUSD"],

    # Payments / remittances
    "payments_remittance": ["XRPUSD", "XLMUSD", "BTCUSD"],

    # Compute / AI-ish infra
    "compute_ai_infra": ["FETUSD", "TAOUSD", "RENDERUSD", "BTCUSD"],
    "decentralized_storage": ["FILUSD", "RENDERUSD", "BTCUSD"],  # optional overlap basket
}


