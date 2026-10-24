/** Phase 1 decimal policy shared with core/decimals.py.

Forms and API payloads still send integer quantities. These constants are the
precision Phase 2 must use; they do not change current calculations.
*/
export const QUANTITY_PLACES = 4;
export const CURRENCY_PLACES = 2;
export const AVERAGE_COST_PLACES = 6;
export const ROUNDING = "half-up";
