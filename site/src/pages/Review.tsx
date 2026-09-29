import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PathRail, pathToggleLabel } from "../components/Journey";
import { Shell } from "../components/Shell";
import { useJourney } from "../lib/journeyState";
import { session, store, useStore } from "../lib/app";
import { ankiCsv, download } from "../lib/anki";
import { allFlashcards } from "../lib/content";
import { dueCards, logEvent } from "../lib/progress";
import { localDate, preview, review, type CardState, type Grade } from "../lib/srs";

const GRADES: { g: Grade; label: string; key: string }[] = [
  { g: "again", label: "Again", key: "1" },
  { g: "hard", label: "Hard", key: "2" },
  { g: "good", label: "Good", key: "3" },
  { g: "easy", label: "Easy", key: "4" },
];

export function Review() {
  useStore();
  const v = useJourney();
  const now = new Date();
  const due = dueCards(store, now);
  const [shown, setShown] = useState(false);
  const [reviewed, setReviewed] = useState(0);
  const current = due[0];

  const grade = (g: Grade) => {
    if (!current) return;
    const before = current.state;
    const after = review(before, g, new Date());
    store.put<CardState>("flashcard_state", current.card.id, after);
    store.put("review_log", crypto.randomUUID(), { card_id: current.card.id, grade: GRADES.findIndex((x) => x.g === g), reviewed_at: after.last_reviewed,
      interval_before: before.interval_days, interval_after: after.interval_days, ease_before: before.ease, ease_after: after.ease });
    setReviewed((n) => n + 1);
    setShown(false);
    if (due.length === 1) logEvent(store, session.id, "cards_reviewed", `${reviewed + 1} card(s)`);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "TEXTAREA" || (e.target as HTMLElement)?.tagName === "INPUT") return;
      if (!current) return;
      if (!shown && (e.key === " " || e.key === "Enter")) {
        e.preventDefault();
        setShown(true);
      } else if (shown) {
        const hit = GRADES.find((x) => x.key === e.key);
        if (hit) grade(hit.g);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const states = store.all<CardState>("flashcard_state");
  const upcoming = states.map((s) => s.data.due).filter((d) => d > localDate(now)).sort()[0];
  const intervals = current ? preview(current.state, now) : null;

  return (
    <Shell rail={<PathRail v={v} />} railToggle={pathToggleLabel(v)}>
      <div className="content">
      <h1>Review</h1>
      <p className="lede">
        Spaced repetition (SM-2): cards you know come back later and later, cards you miss come back tomorrow.
        {" "}{states.length} of {allFlashcards().length} cards are in your queue (a lesson's cards join when you finish it).
      </p>
      {current ? (
        <section className="flashcard section" data-testid="flashcard" aria-label="Flashcard">
          <div className="small-text">Lesson {current.card.lessonId} · {due.length} due{reviewed ? ` · ${reviewed} reviewed this session` : ""}</div>
          <div className="face" data-testid="card-front"><span className="visually-hidden">Question: </span>{current.card.q}</div>
          {shown ? (
            <>
              <hr />
              <div className="face" data-testid="card-back"><span className="visually-hidden">Answer: </span>{current.card.a}</div>
              <div className="grades" role="group" aria-label="How well did you remember?">
                {GRADES.map(({ g, label, key }) => (
                  <button key={g} type="button" onClick={() => grade(g)} data-testid={`grade-${g}`}>
                    {label}
                    <small>{intervals![g]} day{intervals![g] === 1 ? "" : "s"} · key {key}</small>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <button type="button" className="primary" onClick={() => setShown(true)} data-testid="show-answer">Show answer (space)</button>
          )}
        </section>
      ) : (
        <section className="section empty" data-testid="nothing-due">
          <h2>{reviewed ? `Done: ${reviewed} card${reviewed === 1 ? "" : "s"} reviewed.` : "Nothing due today."}</h2>
          <p>{upcoming ? `Next cards are due on ${upcoming}.` : states.length ? "" : "Finish a lesson to add its cards."} <Link to="/">Back to Home</Link></p>
        </section>
      )}
      <section className="section" style={{ borderTop: "1px solid var(--rule)", paddingTop: 24 }}>
        <h2>Anki (optional)</h2>
        <p className="sub">The same cards as a CSV for Anki (File → Import, Basic, comma-separated). Reviews in Anki are not synced back here.</p>
        <button type="button" onClick={() => download("tsfm-rc-flashcards.csv", ankiCsv(), "text/csv")}>Download Anki CSV</button>
      </section>
      </div>
    </Shell>
  );
}
