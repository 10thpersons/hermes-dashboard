"""Shopee Affiliate Open API client (GraphQL + SHA256 signed auth).

Official endpoints:
  MY  https://open-api.affiliate.shopee.com.my/graphql
  ID  https://open-api.affiliate.shopee.co.id/graphql

Auth header format:
  Authorization: SHA256 Credential={app_id}, Timestamp={ts}, Signature={sig}
  Signature = SHA256(app_id + timestamp + payload + secret)

This is the sanctioned way to discover products - no scraping required.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import SETTINGS

TIMEOUT = 30


class ShopeeAuthError(RuntimeError):
    pass


class ShopeeError(RuntimeError):
    pass


@dataclass
class Product:
    item_id: int
    name: str
    offer_link: str
    product_link: str
    price_min: float
    price_max: float
    commission_rate: float
    commission_est: float
    sales: int
    rating: float
    shop_name: str
    shop_id: int
    image_url: str
    discount_rate: int
    raw: dict[str, Any]

    def short(self) -> str:
        return (
            f"{self.name[:60]} | RM{self.price_min:g}-{self.price_max:g} | "
            f"{self.commission_rate*100:.1f}% | est RM{self.commission_est:.2f} | "
            f"sold {self.sales} | {self.rating:.1f}* | {self.shop_name[:24]}"
        )


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


class ShopeeOpenAPI:
    def __init__(self, app_id: str | None = None, secret: str | None = None,
                 endpoint: str | None = None, session: requests.Session | None = None):
        self.app_id = app_id or SETTINGS.shopee_app_id
        self.secret = secret or SETTINGS.shopee_secret
        self.endpoint = endpoint or SETTINGS.shopee_graphql
        self.session = session or requests.Session()

    # ------------------------------------------------------------------ auth
    def _auth_header(self, payload: str) -> str:
        ts = int(time.time())
        sig = hashlib.sha256(f"{self.app_id}{ts}{payload}{self.secret}".encode()).hexdigest()
        return f"SHA256 Credential={self.app_id}, Timestamp={ts}, Signature={sig}"

    def query(self, gql: str, variables: dict | None = None) -> dict:
        if not self.app_id or not self.secret:
            raise ShopeeAuthError(
                "Shopee API credentials missing. Need SHOPEE_API_APP_ID and SHOPEE_API_SECRET."
            )
        payload = json.dumps({"query": gql, "variables": variables or {}}, separators=(",", ":"))
        headers = {
            "Authorization": self._auth_header(payload),
            "Content-Type": "application/json",
        }
        r = self.session.post(self.endpoint, data=payload.encode(), headers=headers, timeout=TIMEOUT)
        if r.status_code in (401, 403):
            raise ShopeeAuthError(f"Shopee rejected credentials (HTTP {r.status_code}).")
        if r.status_code >= 500:
            raise ShopeeError(f"Shopee upstream error HTTP {r.status_code}")
        try:
            data = r.json()
        except ValueError:
            raise ShopeeError(f"Non-JSON response from Shopee: {r.text[:200]}")
        if data.get("errors"):
            msgs = "; ".join(e.get("message", str(e)) for e in data["errors"])
            raise ShopeeError(f"GraphQL errors: {msgs}")
        return data.get("data") or {}

    # -------------------------------------------------------------- products
    def product_offers(self, keyword: str, limit: int = 20, page: int = 1,
                       list_type: int = 1, sort_type: int = 5) -> list[Product]:
        """list_type: 0=recommended 1=highest commission 2=top performance
        sort_type: 1=relevance 2=most sold 3=price high 4=price low 5=commission"""
        gql = """
        query ProductOffers($keyword: String!, $listType: Int, $sortType: Int, $page: Int, $limit: Int) {
          productOfferV2(keyword: $keyword, listType: $listType, sortType: $sortType, page: $page, limit: $limit) {
            nodes {
              itemId productName offerLink productLink imageUrl
              priceMin priceMax priceDiscountRate sales ratingStar
              commissionRate commission sellerCommissionRate shopeeCommissionRate
              shopId shopName
            }
            pageInfo { page limit hasNextPage }
          }
        }
        """
        data = self.query(gql, {
            "keyword": keyword, "listType": list_type, "sortType": sort_type,
            "page": page, "limit": limit,
        })
        nodes = (data.get("productOfferV2") or {}).get("nodes") or []
        return [self._to_product(n) for n in nodes]

    def shopee_offers(self, keyword: str = "", limit: int = 20, page: int = 1,
                      sort_type: int = 1) -> list[Product]:
        """Shopee's own campaigns - official promos, already affiliate-tracked."""
        gql = """
        query ShopeeOffers($keyword: String, $sortType: Int, $page: Int, $limit: Int) {
          shopeeOfferV2(keyword: $keyword, sortType: $sortType, page: $page, limit: $limit) {
            nodes {
              itemId offerName offerLink originalLink imageUrl
              priceMin priceMax priceDiscountRate sales ratingStar
              commissionRate commission shopId shopName
            }
            pageInfo { page limit hasNextPage }
          }
        }
        """
        data = self.query(gql, {
            "keyword": keyword or None, "sortType": sort_type, "page": page, "limit": limit,
        })
        nodes = (data.get("shopeeOfferV2") or {}).get("nodes") or []
        return [self._to_product(n) for n in nodes]

    @staticmethod
    def _to_product(n: dict) -> Product:
        rate = _f(n.get("commissionRate"))
        return Product(
            item_id=_i(n.get("itemId")),
            name=(n.get("productName") or n.get("offerName") or "").strip(),
            offer_link=(n.get("offerLink") or "").strip(),
            product_link=(n.get("productLink") or n.get("originalLink") or "").strip(),
            price_min=_f(n.get("priceMin")),
            price_max=_f(n.get("priceMax")),
            commission_rate=rate,
            commission_est=_f(n.get("commission")),
            sales=_i(n.get("sales")),
            rating=_f(n.get("ratingStar")),
            shop_name=(n.get("shopName") or "").strip(),
            shop_id=_i(n.get("shopId")),
            image_url=(n.get("imageUrl") or "").strip(),
            discount_rate=_i(n.get("priceDiscountRate")),
            raw=n,
        )

    # ----------------------------------------------------------------- links
    def short_link(self, origin_url: str, sub_ids: list[str] | None = None) -> str:
        """Wrap any Shopee URL with affiliate tracking. subIds show up as utm_content."""
        gql = """
        mutation ShortLink($originUrl: String!, $subIds: [String!]) {
          generateShortLink(input: {originUrl: $originUrl, subIds: $subIds}) { shortLink }
        }
        """
        data = self.query(gql, {"originUrl": origin_url, "subIds": sub_ids or []})
        return (data.get("generateShortLink") or {}).get("shortLink", "")

    def offer_link_for(self, product: Product, sub_ids: list[str] | None = None) -> str:
        """Prefer the offerLink (already tracked). Fall back to generateShortLink."""
        if product.offer_link:
            return product.offer_link
        if product.product_link:
            return self.short_link(product.product_link, sub_ids)
        return ""

    # -------------------------------------------------------------- reporting
    def conversion_report(self, limit: int = 20) -> list[dict]:
        gql = """
        query Conversions($limit: Int) {
          conversionReport(limit: $limit) {
            nodes { conversionId purchaseTime totalCommission orderId }
            pageInfo { scrollId }
          }
        }
        """
        try:
            data = self.query(gql, {"limit": limit})
        except (ShopeeError, ShopeeAuthError):
            return []
        return (data.get("conversionReport") or {}).get("nodes") or []

    def health(self) -> str:
        try:
            self.product_offers("organiser", limit=1)
            return "shopee api: OK"
        except ShopeeAuthError as e:
            return f"shopee api: AUTH ({e})"
        except ShopeeError as e:
            return f"shopee api: ERROR ({e})"
        except Exception as e:  # noqa: BLE001
            return f"shopee api: UNREACHABLE ({type(e).__name__})"
