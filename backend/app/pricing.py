from decimal import Decimal


MODEL_PRICING_PER_1M_TOKENS: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4.1": (Decimal("2.00"), Decimal("8.00")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("1.60")),
    "gpt-4.1-nano": (Decimal("0.10"), Decimal("0.40")),
}


def estimate_cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> Decimal:
    if not model:
        return Decimal("0")

    normalized_model = model.lower()
    pricing = MODEL_PRICING_PER_1M_TOKENS.get(normalized_model)
    if pricing is None:
        return Decimal("0")

    input_price, output_price = pricing
    input_cost = Decimal(input_tokens) * input_price / Decimal(1_000_000)
    output_cost = Decimal(output_tokens) * output_price / Decimal(1_000_000)
    return (input_cost + output_cost).quantize(Decimal("0.00000001"))

