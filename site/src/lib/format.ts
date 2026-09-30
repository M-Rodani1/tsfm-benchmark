// Display formats shared by the pages (dates as "26 Nov 2024", durations as "2 h 40 min").

// fixed three-letter months: locales disagree ("Sep" / "Sept"), and the site shows one format
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n: number) => String(n).padStart(2, "0");

/** "2024-11-26" (a calendar date, no time zone) -> "26 Nov 2024". */
export function fmtDate(isoDate: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  if (!m || +m[2] < 1 || +m[2] > 12) return isoDate;
  return `${+m[3]} ${MONTHS[+m[2] - 1]} ${m[1]}`;
}

/** A moment in local time: "14:05" today, "28 Sep, 14:05" otherwise. */
export function fmtMoment(iso: string, now = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  if (d.toDateString() === now.toDateString()) return time;
  return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${time}`;
}

export function fmtDuration(seconds: number): string {
  const m = Math.round(seconds / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

export const capitalise = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];
/** 9 -> "nine" (small counts in prose), larger numbers as digits. */
export const numberWord = (n: number) => WORDS[n] ?? String(n);
