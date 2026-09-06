const MONEY = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "BRL",
  currencyDisplay: "narrowSymbol",
  maximumFractionDigits: 0,
});

const COUNT = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });

export const EMPTY = "—";

function toNumber(v: string | number | null | undefined) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function money(v: string | number | null | undefined) {
  const n = toNumber(v);
  return n === null ? EMPTY : MONEY.format(n);
}

export function moneyCompact(v: string | number | null | undefined) {
  const n = toNumber(v);
  if (n === null) return EMPTY;
  const abs = Math.abs(n);
  if (abs >= 10000) return `${n < 0 ? "-" : ""}R$ ${(abs / 10000).toFixed(1)} 万`;
  return MONEY.format(n);
}

export function axisMoney(v: number) {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(1)}万`;
  if (abs >= 1000) return `${sign}${(abs / 1000).toFixed(1)}千`;
  return `${sign}${abs}`;
}

export function count(v: string | number | null | undefined) {
  const n = toNumber(v);
  return n === null ? EMPTY : COUNT.format(n);
}

export function num(v: string | number | null | undefined, digits = 2) {
  const n = toNumber(v);
  return n === null ? EMPTY : n.toFixed(digits);
}

export function ratio(v: number | null | undefined, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return EMPTY;
  return `${(v * 100).toFixed(digits)}%`;
}

export function signedPct(v: number | null | undefined, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return EMPTY;
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(digits)}%`;
}

export function trendTone(v: number | null | undefined, invert = false) {
  if (v === null || v === undefined || Number.isNaN(v) || v === 0) return "flat" as const;
  const positive = invert ? v < 0 : v > 0;
  return positive ? ("rise" as const) : ("fall" as const);
}

export function shortDate(iso: string) {
  const [, m, d] = iso.split("-");
  return m && d ? `${Number(m)}/${Number(d)}` : iso;
}
