/**
 * Rupiah amounts: showing them and reading what a person typed. Whole rupiah only.
 */

/** "Rp 850.000" from 850000, "850000" or "850000.00". Empty string when not a number. */
export function formatRupiah(value: number | string): string {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "";
  const digits = Math.trunc(Math.abs(amount)).toString();
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${amount < 0 ? "-" : ""}Rp ${grouped}`;
}

/**
 * The whole-rupiah number a person typed, or null when it is not one.
 * Accepts "850000", "850.000", "Rp 850.000", "850 000". Rejects decimals
 * ("850.000,50", "850000.5") and anything with other characters.
 */
export function parseRupiah(input: string): number | null {
  const compact = input.trim().replace(/^rp\.?\s*/i, "").replace(/\s/g, "");
  if (compact === "") return null;
  const plain = /^\d+$/.test(compact);
  const grouped = /^\d{1,3}(\.\d{3})+$/.test(compact);
  if (!plain && !grouped) return null;
  const amount = Number(compact.replace(/\./g, ""));
  return Number.isSafeInteger(amount) && amount > 0 ? amount : null;
}
