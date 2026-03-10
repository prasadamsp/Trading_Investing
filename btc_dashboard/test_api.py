"""Quick diagnostic — run: python test_api.py"""
import requests, traceback

def test(label, url, params):
    print(f"\n{'='*50}")
    print(f"Testing: {label}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    try:
        resp = requests.get(url, params=params, timeout=10)
        print(f"HTTP status: {resp.status_code}")
        j = resp.json()
        # OKX returns {"code":"0","data":[...]}
        code = j.get("code", j.get("retCode", "?"))
        data = j.get("data", j.get("result", {}).get("list", []))
        print(f"API code: {code}")
        print(f"Records returned: {len(data)}")
        if data:
            print(f"First record: {data[0]}")
        else:
            print(f"Full response: {resp.text[:300]}")
    except Exception:
        traceback.print_exc()

test(
    "OKX Funding Rate",
    "https://www.okx.com/api/v5/public/funding-rate-history",
    {"instId": "BTC-USDT-SWAP", "limit": 3},
)

test(
    "OKX Open Interest",
    "https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume",
    {"ccy": "BTC", "period": "1D"},
)

print("\nDone.")
input("\nPress Enter to close...")
