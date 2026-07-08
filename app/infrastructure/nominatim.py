import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("servicos-bebedouro.geocoding")


class NominatimGeocoder:
    def geocode(self, rua: str, numero: str, bairro: str) -> dict | None:
        settings = get_settings()
        query = f"{rua}, {numero}, {bairro}, Bebedouro, São Paulo, Brasil"
        try:
            response = httpx.get(
                f"{settings.nominatim_base_url}/search",
                params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "br"},
                headers={"User-Agent": settings.nominatim_user_agent},
                timeout=5.0,
            )
            response.raise_for_status()
            results = response.json()
            if not results:
                logger.info("Geocodificação sem resultados para: %s", query)
                return None
            return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}
        except Exception as error:
            logger.warning("Falha na geocodificação (%s): %s", query, error)
            return None
