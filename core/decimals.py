"""Shared decimal policy for money, quantities, conversions, and average cost.

SQLite storage
--------------
SQLite has no fixed-precision DECIMAL type. A column declared DECIMAL, NUMERIC,
or REAL has numeric affinity: whole numbers may be stored as integers, and every
other number is an IEEE-754 binary floating-point value. Decimal fractions such
as 0.10 and average costs at 6 places are not guaranteed to survive that storage.

Phase 1 therefore stores new decimal values as TEXT. The text is the canonical
fixed-point form of a Python ``Decimal`` after the rounding rule below, produced
with ``format(value, "f")`` so scientific notation is never written. Reading the
text back constructs a ``Decimal`` directly. Float values are rejected at the
boundary so a binary value is not quietly turned into a decimal.

Existing INTEGER and REAL columns are unchanged. Current sales, purchases,
returns, stock updates, and profit queries still read and write those columns.
The new TEXT columns stay null until a later phase starts posting them.

Rounding
--------
All three precisions use ``ROUND_HALF_UP``: ties round away from zero.
This matches the existing currency helper.

- Quantity and conversion factors: 4 decimal places.
- Currency amounts: 2 decimal places.
- Average cost: 6 decimal places. Intermediate products may keep extra precision;
  6 places is the persisted and posted precision.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


QUANTITY_PLACES = 4
CURRENCY_PLACES = 2
AVERAGE_COST_PLACES = 6

QUANTITY_QUANTUM = Decimal("0.0001")
CURRENCY_QUANTUM = Decimal("0.01")
AVERAGE_COST_QUANTUM = Decimal("0.000001")
ROUNDING = ROUND_HALF_UP


class DecimalInputError(ValueError):
    """A financial value was missing, binary, or not a base-10 number."""


def parse_decimal(value):
    """Return a Decimal from an int, Decimal, or base-10 string.

    Float and bool are rejected. A float cannot be accepted through ``str(float)``
    because that string can already be a rounded binary value.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise DecimalInputError("binary float values are not accepted in financial calculations")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            raise DecimalInputError("a decimal value is required")
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise DecimalInputError("value is not a base-10 decimal") from exc
    raise DecimalInputError("value is not a base-10 decimal")


def quantize_quantity(value):
    return parse_decimal(value).quantize(QUANTITY_QUANTUM, rounding=ROUNDING)


def quantize_currency(value):
    return parse_decimal(value).quantize(CURRENCY_QUANTUM, rounding=ROUNDING)


def quantize_average_cost(value):
    return parse_decimal(value).quantize(AVERAGE_COST_QUANTUM, rounding=ROUNDING)


def decimal_to_text(value):
    """Canonical TEXT storage form. Trailing zeros keep the declared precision."""
    if not isinstance(value, Decimal):
        raise DecimalInputError("only a Decimal can be stored")
    return format(value, "f")


def quantity_to_storage(value):
    return decimal_to_text(quantize_quantity(value))


def currency_to_storage(value):
    return decimal_to_text(quantize_currency(value))


def average_cost_to_storage(value):
    return decimal_to_text(quantize_average_cost(value))


def decimal_from_storage(value):
    """Read TEXT storage. NULL stays None. Float is never accepted."""
    if value is None:
        return None
    if isinstance(value, float):
        raise DecimalInputError("binary float values are not accepted from storage")
    return parse_decimal(value)


def convert_to_base_quantity(quantity, conversion_factor):
    """Convert a selling or purchase quantity into base units.

    Both inputs use 4 decimal places. The product is quantized back to 4 places.
    This helper is not used by sales, purchases, or returns in Phase 1.
    """
    qty = quantize_quantity(quantity)
    factor = quantize_quantity(conversion_factor)
    if qty <= 0 or factor <= 0:
        raise DecimalInputError("quantity and conversion factor must be positive")
    return quantize_quantity(qty * factor)
