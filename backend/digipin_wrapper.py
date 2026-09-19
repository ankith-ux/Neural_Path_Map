def encode_digipin(lat: float, lng: float) -> str:
    try:
        import digipin

        return digipin.encode(lat, lng)
    except Exception:
        lat_key = f"{abs(lat):.5f}".replace(".", "")
        lng_key = f"{abs(lng):.5f}".replace(".", "")
        return f"DIGIPIN-{lat_key}-{lng_key}"
